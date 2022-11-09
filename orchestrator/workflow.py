# Copyright 2019-2020 SURF.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from __future__ import annotations

import functools
import inspect
import sys
from dataclasses import asdict, dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    NoReturn,
    Optional,
    Protocol,
    TypeVar,
    Union,
    cast,
    overload,
    runtime_checkable,
)
from uuid import UUID

import structlog
from nwastdlib import const, identity
from structlog.stdlib import BoundLogger

if sys.version_info >= (3, 10):
    from structlog.contextvars import bound_contextvars
else:
    from structlog.threadlocal import tmp_bind

from orchestrator.config.assignee import Assignee
from orchestrator.db import EngineSettingsTable, db, transactional
from orchestrator.forms import FormPage
from orchestrator.targets import Target
from orchestrator.types import (
    ErrorDict,
    FormGenerator,
    InputFormGenerator,
    InputStepFunc,
    State,
    StateInputFormGenerator,
    StateInputStepFunc,
    StateSimpleInputFormGenerator,
    StepFunc,
    strEnum,
)
from orchestrator.utils.docs import make_workflow_doc
from orchestrator.utils.errors import error_state_to_dict
from orchestrator.utils.state import form_inject_args, inject_args

logger = structlog.get_logger(__name__)


StepLogFunc = Callable[["ProcessStat", "Step", "Process"], "Process"]
StepLogFuncInternal = Callable[["Step", "Process"], "Process"]
StepToProcessFunc = Callable[[State], "Process"]


@runtime_checkable
class Step(Protocol):
    __name__: str
    __qualname__: str
    name: str
    form: Optional[InputFormGenerator]
    assignee: Optional[Assignee]

    def __call__(self, state: State) -> Process:
        ...


@runtime_checkable
class Workflow(Protocol):
    __name__: str
    __qualname__: str
    name: str
    description: str
    initial_input_form: Optional[InputFormGenerator] = None
    target: Optional[Target] = None
    steps: StepList

    def __call__(self) -> NoReturn:
        ...


def make_step_function(
    f: Callable, name: str, form: Optional[InputFormGenerator] = None, assignee: Optional[Assignee] = Assignee.SYSTEM
) -> Step:
    step_func = cast(Step, f)

    step_func.name = name
    step_func.form = form
    step_func.assignee = assignee
    return step_func


class StepList(List[Step]):
    """Wraps around a primitive list of `Step` to provide a "list" with associative `append` (or its alias: `>>`).

    >>> one = step("one")(dict)
    >>> two = step("two")(dict)
    >>> three = step("three")(dict)

    >>> empty = StepList([])
    >>> empty >> empty
    StepList []

    >>> empty == empty >> empty
    True

    >>> str(empty >> one)
    'StepList [one]'

    >>> (begin >> one >> two) >> three == begin >> one >> (begin >> two >> three)
    True
    """

    def map(self, f: Callable) -> StepList:
        return StepList(map(f, self))

    @overload  # type: ignore
    def __getitem__(self, i: int) -> Step:
        ...

    @overload
    def __getitem__(self, i: slice) -> StepList:
        ...

    def __getitem__(self, i: Union[int, slice]) -> Union[Step, StepList]:
        retval: Union[Step, List[Step]] = super().__getitem__(i)
        if isinstance(retval, list):
            # ensure we return a StepList and not a regular list.
            retval = type(self)(retval)
        return retval

    def __rshift__(self, other: Union[StepList, Step]) -> StepList:
        if isinstance(other, Step):
            return StepList([*self, other])
        elif isinstance(other, StepList):
            return StepList([*self, *other])
        elif hasattr(other, "__name__"):  # type:ignore
            raise ValueError(
                f"Expected @step decorated function or type Step or StepList, got {type(other)} with name {other.__name__} instead."
            )
        else:
            raise ValueError(f"Expected @step decorated function or type Step or StepList, got {type(other)} instead.")

    def __str__(self) -> str:
        return f"StepList [{', '.join(x.name for x in self)}]"

    def __repr__(self) -> str:
        return f"StepList [{', '.join(repr(x) for x in self)}]"


def _handle_simple_input_form_generator(f: StateInputStepFunc) -> StateInputFormGenerator:
    if inspect.isgeneratorfunction(f):
        return cast(StateInputFormGenerator, f)
    if inspect.isgenerator(f):
        raise ValueError("Got a generator object instead of function, this is not correct")
    else:
        # If f is a SimpleInputFormGenerator convert to new style generator function
        def form_generator(state: State) -> FormGenerator:
            user_input = yield cast(StateSimpleInputFormGenerator, f)(state)
            return user_input.dict()

        return form_generator


def make_workflow(
    f: Callable,
    description: str,
    initial_input_form: Optional[InputStepFunc],
    target: Optional[Target],
    steps: StepList,
) -> Workflow:
    @functools.wraps(f)
    def wrapping_function() -> NoReturn:
        raise Exception("This function should not be executed")

    wrapping_function = cast(Workflow, wrapping_function)

    wrapping_function.name = f.__name__  # default, will be changed by LazyWorkflowInstance
    wrapping_function.description = description

    if initial_input_form is None:
        # We always need a form to prevent starting a workflow when no input is needed.
        # This would happen on first post that is used to retrieve the first form page
        initial_input_form = cast(InputStepFunc, const(FormPage))

    wrapping_function.initial_input_form = _handle_simple_input_form_generator(initial_input_form)
    wrapping_function.target = target
    wrapping_function.steps = steps

    wrapping_function.__doc__ = make_workflow_doc(wrapping_function)

    return wrapping_function


def step(name: str) -> Callable[[StepFunc], Step]:
    """Mark a function as a workflow step."""

    def decorator(func: StepFunc) -> Step:
        @functools.wraps(func)
        def wrapper(state: State) -> Process:
            if sys.version_info >= (3, 10):
                with bound_contextvars(func=func.__qualname__):
                    step_in_inject_args = inject_args(func)
                    try:
                        with transactional(db, logger):
                            result = step_in_inject_args(state)
                            return Success(result)
                    except Exception as ex:
                        logger.warning("Step failed", exc_info=ex)
                        return Failed(ex)
            else:
                with tmp_bind(logger, func=func.__qualname__) as log:
                    step_in_inject_args = inject_args(func)
                    try:
                        with transactional(db, log):
                            result = step_in_inject_args(state)
                            return Success(result)
                    except Exception as ex:
                        log.warning("Step failed", exc_info=ex)
                        return Failed(ex)

        return make_step_function(wrapper, name)

    return decorator


def retrystep(name: str) -> Callable[[StepFunc], Step]:
    """Mark a function as a retryable workflow step.

    If this step fails it goes to `Waiting` were it will be retried periodically. If it `Success` it acts as a normal
    step.
    """

    def decorator(func: StepFunc) -> Step:
        @functools.wraps(func)
        def wrapper(state: State) -> Process:
            if sys.version_info >= (3, 10):
                with bound_contextvars(func=func.__qualname__):
                    step_in_inject_args = inject_args(func)
                    try:
                        with transactional(db, logger):
                            result = step_in_inject_args(state)
                            return Success(result)
                    except Exception as ex:
                        return Waiting(ex)

            else:
                with tmp_bind(logger, func=func.__qualname__) as log:
                    step_in_inject_args = inject_args(func)
                    try:
                        with transactional(db, log):
                            result = step_in_inject_args(state)
                            return Success(result)
                    except Exception as ex:
                        return Waiting(ex)

        return make_step_function(wrapper, name)

    return decorator


def inputstep(name: str, assignee: Optional[Assignee] = None) -> Callable[[InputStepFunc], Step]:
    """Add user input step to workflow.

    IMPORTANT: In contrast to other workflow steps, the `@inputstep` wrapped function will not run in the
    workflow engine! This means that it should never do any changes in the database and external systems!

    Example::

        @inputstep("User step", assignee=Assignee.NOC)
        def user_step(state: State) -> FormGenerator:
            class Form(FormPage):
                name: str
            user_input = yield Form
            return {**user_input.dict(), "some extra key": True}

    """

    def decorator(func: InputStepFunc) -> Step:
        def wrapper(state: State) -> FormGenerator:
            form_generator_in_form_inject_args = form_inject_args(func)

            form_generator = _handle_simple_input_form_generator(form_generator_in_form_inject_args)

            return form_generator(state)

        @functools.wraps(func)
        def suspend(state: State) -> Process:
            return Suspend(state)

        return make_step_function(suspend, name, wrapper, assignee)

    return decorator


def _purestep(name: str) -> Callable[[StepToProcessFunc], StepList]:
    """Part of workflow "DSL" to map a `state -> Process state` function into a workflow step."""

    def _purestep(f: StepToProcessFunc) -> StepList:
        return StepList([make_step_function(f, name)])

    return _purestep


def conditional(p: Callable[[State], bool]) -> Callable[..., StepList]:
    """Use a predicate to control whether or not a step is run."""

    def _conditional(steps_or_func: Union[StepList, Step]) -> StepList:
        if isinstance(steps_or_func, Step):
            steps = StepList([steps_or_func])
        else:
            steps = steps_or_func

        def wrap(step: Step) -> Step:
            @functools.wraps(step)
            def wrapper(state: State) -> Process:
                return step(state) if p(state) else Skipped(state)

            return make_step_function(wrapper, step.name, step.form, step.assignee)

        return steps.map(wrap)

    return _conditional


def steplens(get: Callable[[State], State], set: Callable[[State], Callable[[State], State]]) -> Callable[[Step], Step]:
    """Update a step list to zoom its input state using get and update its output state using set."""

    def wrap(step: Step) -> Step:
        @functools.wraps(step)
        def wrapper(state: State) -> Process:
            sub_state = get(state)

            result: Process = step(sub_state)

            if result.isfailed() or result.iswaiting():
                return result
            else:
                return result.map(set(state))

        return make_step_function(wrapper, step.name, step.form, step.assignee)

    return wrap


def focussteps(key: str) -> Callable[[Union[Step, StepList]], StepList]:
    """Return a function that maps `steplens` over `steps`, getting and setting a single key."""

    def zoom(steps_or_func: Union[Step, StepList]) -> StepList:
        if isinstance(steps_or_func, Step):
            steps = StepList([steps_or_func])
        else:
            steps = steps_or_func

        def get(state: State) -> State:
            return state.get(key, {})

        def set(state: State) -> Callable[[State], State]:
            return lambda substate: {**state, key: substate}

        return steps.map(steplens(get, set))

    return zoom


def workflow(
    description: str, initial_input_form: Optional[InputStepFunc] = None, target: Optional[Target] = None
) -> Callable[[Callable[[], StepList]], Workflow]:
    """Transform an initial_input_form and a step list into a workflow.

    Use this for other workflows. For create workflows use :func:`create_workflow`

    Example::

        @workflow("create service port")
        def create_service_port():
            init
            << do_something
            << done
    """
    if initial_input_form is None:
        initial_input_form_in_form_inject_args = None
    else:
        initial_input_form_in_form_inject_args = form_inject_args(initial_input_form)

    def _workflow(f: Callable[[], StepList]) -> Workflow:
        return make_workflow(f, description, initial_input_form_in_form_inject_args, target, f())

    return _workflow


@dataclass
class ProcessStat:
    pid: UUID
    workflow: Workflow
    state: Process
    log: StepList
    current_user: str

    def update(self, **vs: Any) -> ProcessStat:
        """Update ProcessStat.

        >>> pstat = ProcessStat('', None, {}, [], "")
        >>> pstat.update(state={"a": "b"})
        ProcessStat(pid='', workflow=None, state={'a': 'b'}, log=[], current_user='')
        """
        return ProcessStat(**{**asdict(self), **vs})


S = TypeVar("S")
F = TypeVar("F")


class ProcessStatus(strEnum):
    CREATED = "created"
    RUNNING = "running"
    SUSPENDED = "suspended"
    WAITING = "waiting"
    ABORTED = "aborted"
    FAILED = "failed"
    API_UNAVAILABLE = "api_unavailable"
    INCONSISTENT_DATA = "inconsistent_data"
    COMPLETED = "completed"


class StepStatus(strEnum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    SUSPEND = "suspend"
    WAITING = "waiting"
    FAILED = "failed"
    ABORT = "abort"
    COMPLETE = "complete"


class Process(Generic[S]):
    def __init__(self, s: S):
        self.s = s

    def map(self, f: Callable[[S], S]) -> Process[S]:
        """Apply a function to the process.

        >>> inc = lambda n: n + 1

        >>> Success(1).map(inc)
        Success 2

        >>> Skipped(1).map(inc)
        Skipped 2

        >>> Suspend(1).map(inc)
        Suspend 2

        >>> Waiting(1).map(inc)
        Waiting 2

        >>> Abort(1).map(inc)
        Abort 2

        >>> Failed(1).map(inc)
        Failed 2

        >>> Complete(1).map(inc)
        Complete 2
        """

        def g(x: S) -> Process[S]:
            Self = self.__class__
            return Self(f(x))

        return self._fold(g, g, g, g, g, g, g)

    def _fold(
        self,
        success: Callable[[S], F],
        skipped: Callable[[S], F],
        suspend: Callable[[S], F],
        waiting: Callable[[S], F],
        abort: Callable[[S], F],
        failed: Callable[[S], F],
        complete: Callable[[S], F],
    ) -> F:
        """Unwrap the state from the Process category.

        >>> Success('a')._fold(Success, Skipped, Suspend, Waiting, Abort, Failed, Complete)
        Success 'a'

        >>> Skipped('a')._fold(Success, Skipped, Suspend, Waiting, Abort, Failed, Complete)
        Skipped 'a'

        >>> Suspend('a')._fold(Success, Skipped, Suspend, Waiting, Abort, Failed, Complete)
        Suspend 'a'

        >>> Waiting('a')._fold(Success, Skipped, Suspend, Waiting, Abort, Failed, Complete)
        Waiting 'a'

        >>> Abort('a')._fold(Success, Skipped, Suspend, Waiting, Abort, Failed, Complete)
        Abort 'a'

        >>> Failed('a')._fold(Success, Skipped, Suspend, Waiting, Abort, Failed, Complete)
        Failed 'a'

        >>> Complete('a')._fold(Success, Skipped, Suspend, Waiting, Abort, Failed, Complete)
        Complete 'a'

        >>> Process('a')._fold(Success, Skipped, Suspend, Waiting, Abort, Failed, Complete)
        Traceback (most recent call last):
            ...
        NotImplementedError: Abstract function `_fold` must be implemented by the type constructor
        """
        raise NotImplementedError("Abstract function `_fold` must be implemented by the type constructor")

    def unwrap(self) -> S:
        """Get unwrapped state.

        >>> Success('a').unwrap()
        'a'

        >>> Skipped('a').unwrap()
        'a'

        >>> Suspend('a').unwrap()
        'a'

        >>> Waiting('a').unwrap()
        'a'

        >>> Abort('a').unwrap()
        'a'

        >>> Failed('a').unwrap()
        'a'

        >>> Complete('a').unwrap()
        'a'
        """
        return self._fold(identity, identity, identity, identity, identity, identity, identity)  # type: ignore

    def issuccess(self) -> bool:
        """Test if this instance is Success.

        >>> Success('a').issuccess()
        True

        >>> Skipped('a').issuccess()
        False

        >>> Suspend('a').issuccess()
        False

        >>> Waiting('a').issuccess()
        False

        >>> Abort('a').issuccess()
        False

        >>> Failed('a').issuccess()
        False

        >>> Complete('a').issuccess()
        False
        """
        return self._fold(
            const(True), const(False), const(False), const(False), const(False), const(False), const(False)
        )

    def isskipped(self) -> bool:
        """Test if this instance is Skipped.

        >>> Success('a').isskipped()
        False

        >>> Skipped('a').isskipped()
        True

        >>> Suspend('a').isskipped()
        False

        >>> Waiting('a').isskipped()
        False

        >>> Abort('a').isskipped()
        False

        >>> Failed('a').isskipped()
        False

        >>> Complete('a').isskipped()
        False
        """
        return self._fold(
            const(False), const(True), const(False), const(False), const(False), const(False), const(False)
        )

    def issuspend(self) -> bool:
        """Test if this instance is Suspend.

        >>> Success('a').issuspend()
        False

        >>> Skipped('a').issuspend()
        False

        >>> Suspend('a').issuspend()
        True

        >>> Waiting('a').issuspend()
        False

        >>> Abort('a').issuspend()
        False

        >>> Failed('a').issuspend()
        False

        >>> Complete('a').issuspend()
        False
        """
        return self._fold(
            const(False), const(False), const(True), const(False), const(False), const(False), const(False)
        )

    def isabort(self) -> bool:
        """Test if this instance is Abort.

        >>> Success('a').isabort()
        False

        >>> Skipped('a').isabort()
        False

        >>> Suspend('a').isabort()
        False

        >>> Waiting('a').isabort()
        False

        >>> Abort('a').isabort()
        True

        >>> Failed('a').isabort()
        False

        >>> Complete('a').isabort()
        False
        """
        return self._fold(
            const(False), const(False), const(False), const(False), const(True), const(False), const(False)
        )

    def iswaiting(self) -> bool:
        """Test if this instance is Waiting.

        >>> Success('a').iswaiting()
        False

        >>> Skipped('a').iswaiting()
        False

        >>> Suspend('a').iswaiting()
        False

        >>> Waiting('a').iswaiting()
        True

        >>> Abort('a').iswaiting()
        False

        >>> Failed('a').iswaiting()
        False

        >>> Complete('a').iswaiting()
        False
        """
        return self._fold(
            const(False), const(False), const(False), const(True), const(False), const(False), const(False)
        )

    def isfailed(self) -> bool:
        """Test if this instance is Waiting.

        >>> Success('a').isfailed()
        False

        >>> Skipped('a').isfailed()
        False

        >>> Suspend('a').isfailed()
        False

        >>> Waiting('a').isfailed()
        False

        >>> Abort('a').isfailed()
        False

        >>> Failed('a').isfailed()
        True

        >>> Complete('a').isfailed()
        False
        """
        return self._fold(
            const(False), const(False), const(False), const(False), const(False), const(True), const(False)
        )

    def iscomplete(self) -> bool:
        """Test if this instance is Complete.

        >>> Success('a').iscomplete()
        False

        >>> Skipped('a').iscomplete()
        False

        >>> Suspend('a').iscomplete()
        False

        >>> Waiting('a').iscomplete()
        False

        >>> Abort('a').iscomplete()
        False

        >>> Failed('a').iscomplete()
        False

        >>> Complete('a').iscomplete()
        True
        """
        return self._fold(
            const(False), const(False), const(False), const(False), const(False), const(False), const(True)
        )

    def __eq__(self, other: object) -> bool:
        """Test two instances for equality.

        >>> Success('a') == Success('a')
        True

        >>> Success('a') != Success('b')
        True

        >>> Success('a') != Suspend('a')
        True

        >>> Success('a') != Waiting('a')
        True

        >>> Suspend('a') != Abort('a')
        True

        >>> Success('a') != 'a'
        True
        """
        return self.__class__ == other.__class__ and self.s == cast(Process, other).s

    @property
    def status(self) -> StepStatus:
        """Show status.

        >>> Success({}).status
        <StepStatus.SUCCESS: 'success'>

        >>> Skipped({}).status
        <StepStatus.SKIPPED: 'skipped'>

        >>> Suspend({}).status
        <StepStatus.SUSPEND: 'suspend'>

        >>> Waiting({}).status
        <StepStatus.WAITING: 'waiting'>

        >>> Abort({}).status
        <StepStatus.ABORT: 'abort'>

        >>> Failed({}).status
        <StepStatus.FAILED: 'failed'>

        >>> Complete({}).status
        <StepStatus.COMPLETE: 'complete'>
        """
        return StepStatus[self.__class__.__name__.upper()]

    @staticmethod
    def from_status(status: StepStatus, state: S) -> Optional[Process]:
        """Make Process based on status and state.

        >>> Process.from_status('success', {})
        Success {}

        >>> Process.from_status('skipped', {})
        Skipped {}

        >>> Process.from_status('suspend', {})
        Suspend {}

        >>> Process.from_status('waiting', {})
        Waiting {}

        >>> Process.from_status('abort', {})
        Abort {}

        >>> Process.from_status('failed', {})
        Failed {}

        >>> Process.from_status('complete', {})
        Complete {}

        >>> Process.from_status('unknown', {})

        """
        status_class = _STATUSES.get(status)
        return status_class(state) if status_class else None

    @property
    def overall_status(self) -> ProcessStatus:
        """Show overall status of process or task.

        >>> Success({}).overall_status
        <ProcessStatus.RUNNING: 'running'>

        >>> Skipped({}).overall_status
        <ProcessStatus.RUNNING: 'running'>

        >>> Suspend({}).overall_status
        <ProcessStatus.SUSPENDED: 'suspended'>

        >>> Waiting({}).overall_status
        <ProcessStatus.WAITING: 'waiting'>

        >>> Abort({}).overall_status
        <ProcessStatus.ABORTED: 'aborted'>

        >>> Failed({}).overall_status
        <ProcessStatus.FAILED: 'failed'>

        >>> Complete({}).overall_status
        <ProcessStatus.COMPLETED: 'completed'>
        """
        return self._fold(
            const(ProcessStatus.RUNNING),
            const(ProcessStatus.RUNNING),
            const(ProcessStatus.SUSPENDED),
            const(ProcessStatus.WAITING),
            const(ProcessStatus.ABORTED),
            const(ProcessStatus.FAILED),
            const(ProcessStatus.COMPLETED),
        )

    def __repr__(self) -> str:
        """Show self.

        >>> repr(Success({}))
        'Success {}'

        >>> repr(Skipped({}))
        'Skipped {}'

        >>> repr(Suspend({}))
        'Suspend {}'

        >>> repr(Waiting({}))
        'Waiting {}'

        >>> repr(Abort({}))
        'Abort {}'

        >>> repr(Failed({}))
        'Failed {}'

        >>> repr(Complete({}))
        'Complete {}'
        """
        name = self.__class__.__name__
        return f"{name} {self.s!r}"

    def on_success(self, f: Callable[[S], S]) -> Process[S]:
        """Apply function on Process state only when Success.

        >>> def assign_b(d):
        ...     d["b"] = 2
        ...     return d
        >>> Success({"a":1}).on_success(assign_b)
        Success {'a': 1, 'b': 2}

        >>> Failed({"a": 1}).on_success(assign_b)
        Failed {'a': 1}
        """
        return self.map(f) if self.issuccess() else self

    def on_skipped(self, f: Callable[[S], S]) -> Process[S]:
        """Apply function on Process state only when Skipped."""
        return self.map(f) if self.isskipped() else self

    def on_suspend(self, f: Callable[[S], S]) -> Process[S]:
        """Apply function on Process state only when Suspend."""
        return self.map(f) if self.issuspend() else self

    def on_waiting(self, f: Callable[[S], S]) -> Process[S]:
        """Apply function on Process state only when Waiting."""
        return self.map(f) if self.iswaiting() else self

    def on_abort(self, f: Callable[[S], S]) -> Process[S]:
        """Apply function on Process state only when Abort."""
        return self.map(f) if self.isabort() else self

    def on_failed(self, f: Callable[[S], S]) -> Process[S]:
        """Apply function on Process state only when Failed."""
        return self.map(f) if self.isfailed() else self

    def on_complete(self, f: Callable[[S], S]) -> Process[S]:
        """Apply function on Process state only when Complete."""
        return self.map(f) if self.iscomplete() else self

    def execute_step(self, step: Callable[[S], Process[S]]) -> Process[S]:
        """Execute a step transition based on the a step function.

        A step can only be executed if the current state is success or skipped.

        >>> Success({"a":1}).execute_step(lambda s: Success(s))
        Success {'a': 1}
        >>> Success({"a":1}).execute_step(lambda s: Failed(s))
        Failed {'a': 1}

        >>> Waiting({"a":1}).execute_step(lambda s: Failed(s))
        Waiting {'a': 1}

        """

        return self._fold(step, step, Suspend, Waiting, Abort, Failed, Complete)

    def abort(self) -> Process[S]:
        """Abort process.

        Always works except for completed processes
        """
        return self._fold(Abort, Abort, Abort, Abort, Abort, Abort, Complete)

    def resume(self, resume_suspend: Callable[[Process[S]], Process[S]]) -> Process[S]:
        """Resume process.

        Cannot resume Abort or Complete states

        Args:
            resume_suspend: function to call on resuming a suspended state. Might fail and determine the next state


        >>> Suspend({"a":1}).resume(lambda s: s)
        Success {'a': 1}

        >>> Success({"a":1}).resume(lambda s: Failed({"error": "Exception!!"}))
        Success {'a': 1}

        >>> Failed({"a":1}).resume(lambda s: Failed({"error": "Exception!!"}))
        Success {'a': 1}

        >>> Suspend({"a":1}).resume(lambda s: Failed({"error": "Exception!!"}))
        Failed {'error': 'Exception!!'}
        """

        next_state = self._fold(Success, Success, Success, Success, Abort, Success, Complete)

        if self.issuspend():
            result = resume_suspend(next_state)  # type: ignore
            return result

        return next_state  # type: ignore


class Success(Process[S]):
    def _fold(
        self,
        success: Callable[[S], F],
        skipped: Callable[[S], F],
        suspend: Callable[[S], F],
        waiting: Callable[[S], F],
        abort: Callable[[S], F],
        failed: Callable[[S], F],
        complete: Callable[[S], F],
    ) -> F:
        return success(self.s)


class Skipped(Process[S]):
    def _fold(
        self,
        success: Callable[[S], F],
        skipped: Callable[[S], F],
        suspend: Callable[[S], F],
        waiting: Callable[[S], F],
        abort: Callable[[S], F],
        failed: Callable[[S], F],
        complete: Callable[[S], F],
    ) -> F:
        return skipped(self.s)


class Suspend(Process[S]):
    def _fold(
        self,
        success: Callable[[S], F],
        skipped: Callable[[S], F],
        suspend: Callable[[S], F],
        waiting: Callable[[S], F],
        abort: Callable[[S], F],
        failed: Callable[[S], F],
        complete: Callable[[S], F],
    ) -> F:
        return suspend(self.s)


class Waiting(Process[S]):
    def _fold(
        self,
        success: Callable[[S], F],
        skipped: Callable[[S], F],
        suspend: Callable[[S], F],
        waiting: Callable[[S], F],
        abort: Callable[[S], F],
        failed: Callable[[S], F],
        complete: Callable[[S], F],
    ) -> F:
        return waiting(self.s)


class Abort(Process[S]):
    def _fold(
        self,
        success: Callable[[S], F],
        skipped: Callable[[S], F],
        suspend: Callable[[S], F],
        waiting: Callable[[S], F],
        abort: Callable[[S], F],
        failed: Callable[[S], F],
        complete: Callable[[S], F],
    ) -> F:
        return abort(self.s)


class Failed(Process[S]):
    def _fold(
        self,
        success: Callable[[S], F],
        skipped: Callable[[S], F],
        suspend: Callable[[S], F],
        waiting: Callable[[S], F],
        abort: Callable[[S], F],
        failed: Callable[[S], F],
        complete: Callable[[S], F],
    ) -> F:
        return failed(self.s)


class Complete(Process[S]):
    def _fold(
        self,
        success: Callable[[S], F],
        skipped: Callable[[S], F],
        suspend: Callable[[S], F],
        waiting: Callable[[S], F],
        abort: Callable[[S], F],
        failed: Callable[[S], F],
        complete: Callable[[S], F],
    ) -> F:
        return complete(self.s)


_STATUSES = {
    StepStatus.SUCCESS: Success,
    StepStatus.SKIPPED: Skipped,
    StepStatus.SUSPEND: Suspend,
    StepStatus.WAITING: Waiting,
    StepStatus.ABORT: Abort,
    StepStatus.FAILED: Failed,
    StepStatus.COMPLETE: Complete,
}

_NUM_STATUSES = len(_STATUSES)


def cond_bind(log: BoundLogger, state: Dict[str, Any], key: str, as_key: Optional[str] = None) -> BoundLogger:
    """Conditionally (on presence of key) build Structlog context."""
    if as_key is None:
        as_key = key
    if key in state:
        return log.bind(**{as_key: state[key]})
    return log


def log_mutations(old_process_state: State) -> Callable[[State], None]:
    def _log_mutations(new_process_state: State) -> None:
        mutations = {
            k: v for k, v in new_process_state.items() if k not in old_process_state or old_process_state[k] != v
        }
        logger.debug("Step returned a result state.", mutations=mutations)

    return _log_mutations


def errorlogger(error: ErrorDict) -> None:
    logger.error("Workflow returned an error.", **error)


def _exec_steps(steps: StepList, starting_process: Process, dblogstep: StepLogFuncInternal) -> Process:
    """Execute the workflow steps one by one until a Process state other than Success or Skipped is reached."""
    consolelogger = cond_bind(logger, starting_process.unwrap(), "reporter", "created_by")
    process = starting_process

    for step in steps:
        # Check if we need to continue with the process
        if not (process.issuccess() or process.isskipped()):
            break

        consolelogger = consolelogger.bind(step_name=step.name)

        # Debug logging of step information
        mutationlogger = log_mutations(process.unwrap())

        # Execute step
        try:
            engine_status = EngineSettingsTable.query.one()
            if engine_status.global_lock:
                raise RuntimeWarning("Exiting from thread workflow engine is Paused or Pausing")
            step_result_process = process.execute_step(step)
        except RuntimeWarning:
            consolelogger.info(
                "Not executing Step as the workflow engine is Paused. Process will remain in state 'running'"
            )
            return process
        except Exception as e:
            consolelogger.error("An exception occurred while executing the workflow step.")
            step_result_process = Failed(e)

        # write the new process state after the step execution to the database
        # Convert ErrorState to ErrorDict when Failed or Waiting before writing to the database
        # as bare exceptions are not JSON serializable
        result_to_log = step_result_process.on_failed(error_state_to_dict).on_waiting(error_state_to_dict)
        result_to_log.on_success(mutationlogger).on_failed(errorlogger).on_waiting(errorlogger)

        process = dblogstep(step, result_to_log)

        # If database logging failed, the workflow should fail. When it was successful just continue with the
        # result of the executed step.
        consolelogger.debug("Workflow step executed.", process_status=process.status)

    return process


def runwf(pstat: ProcessStat, logstep: StepLogFunc) -> Process:
    """Run workflow optionally adding extra state.

    The extra state is used on resume and to set initial state
    """
    steps = pstat.log

    def _logstep(*x: Any) -> Process:
        return logstep(pstat, *x)

    logger.bind(workflow=pstat.workflow.name)

    def resume_suspend(process: Process) -> Process:
        step = steps.pop(0)
        return _logstep(step, process)

    next_state = pstat.state.resume(resume_suspend)

    return _exec_steps(steps, next_state, _logstep)


def abort_wf(pstat: ProcessStat, logstep: StepLogFunc) -> Process:
    """Abort a suspended workflow."""

    if not pstat.state.iscomplete():
        abort_func = make_step_function(Abort, "User Aborted")

        state = pstat.state.abort()

        return logstep(pstat, abort_func, state)
    else:
        return pstat.state


@_purestep("Start")
def init(state: State) -> Process:
    """Start of workflow."""
    return Success(state)


@_purestep("Done")
def done(state: State) -> Process:
    """End of workflow."""
    return Complete(state)


@_purestep("Abort")
def abort(state: State) -> Process:
    """End of aborted workflow."""
    return Abort(state)


# A `StepList` constructor to be used in reusable step sequences.
begin = StepList()
