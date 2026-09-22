# Copyright 2019-2026 SURF, GÉANT, ESnet.
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

import contextvars
import functools
import inspect
import secrets
import warnings
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from itertools import dropwhile
from typing import (
    Any,
    Generic,
    Literal,
    NoReturn,
    Protocol,
    TypeVar,
    cast,
    overload,
    runtime_checkable,
)
from uuid import UUID

import strawberry
import structlog
from structlog.contextvars import bound_contextvars
from structlog.stdlib import BoundLogger

from nwastdlib import const, identity
from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.core.config.assignee import Assignee
from orchestrator.core.db import db, transactional
from orchestrator.core.services.settings import get_engine_settings_table
from orchestrator.core.settings import app_settings
from orchestrator.core.targets import Target
from orchestrator.core.types import ErrorDict, StepFunc
from orchestrator.core.utils.auth import Authorizer
from orchestrator.core.utils.datetime import nowtz
from orchestrator.core.utils.docs import make_workflow_doc
from orchestrator.core.utils.errors import error_state_to_dict
from orchestrator.core.utils.state import form_inject_args, inject_args
from pydantic_forms.core import FormPage
from pydantic_forms.types import (
    FormGenerator,
    InputFormGenerator,
    InputStepFunc,
    State,
    StateInputFormGenerator,
    StateInputStepFunc,
    StateSimpleInputFormGenerator,
    strEnum,
)

logger = structlog.get_logger(__name__)

StepLogFunc = Callable[["ProcessStat", "Step", "Process"], "Process"]
StepLogFuncInternal = Callable[["Step", "Process"], "Process"]
StepToProcessFunc = Callable[[State], "Process"]

step_log_fn_var: contextvars.ContextVar[StepLogFuncInternal] = contextvars.ContextVar("log_step_fn")

DEFAULT_CALLBACK_ROUTE_KEY = "callback_route"
CALLBACK_TOKEN_KEY = "__callback_token"  # noqa: S105
DEFAULT_CALLBACK_PROGRESS_KEY = "callback_progress"  # noqa: S105
CALLBACK_TIMEOUT_KEY = "__callback_timeout"

LOOP_SUB_STEP_KEY = "__sub_step"
LOOP_STEP_GROUP_KEY = "__step_group"
LOOP_STEPS_KEY = "loop_steps"
LOOP_STEPS_BRANCHES_KEY = "loop_steps_branches"
LOOP_STEPS_BODIES_KEY = "loop_steps_bodies"


@runtime_checkable
class Step(Protocol):
    __name__: str
    __qualname__: str
    name: str
    form: InputFormGenerator | None
    assignee: Assignee | None
    resume_auth_callback: Authorizer | None = None
    retry_auth_callback: Authorizer | None = None

    def __call__(self, state: State) -> Process: ...


@dataclass(frozen=True)
class RunPredicatePass:
    """Return this from a run predicate to allow the workflow to start."""

    def __bool__(self) -> bool:
        return True


@dataclass(frozen=True)
class RunPredicateFail:
    """Return this from a run predicate to block the workflow from starting."""

    message: str

    def __bool__(self) -> bool:
        return False


RunPredicateResult = RunPredicatePass | RunPredicateFail
RunPredicate = Callable[..., RunPredicateResult]


@runtime_checkable
class Workflow(Protocol):
    __name__: str
    __qualname__: str
    name: str
    description: str
    authorize_callback: Authorizer
    retry_auth_callback: Authorizer
    initial_input_form: InputFormGenerator
    target: Target
    steps: StepList
    run_predicate: RunPredicate | None = None

    def __call__(self) -> NoReturn: ...


@dataclass(frozen=True)
class PredicateContext:
    """Context passed as the first argument to a workflow's run predicate."""

    workflow: Workflow
    workflow_key: str


def make_step_function(
    f: Callable,
    name: str,
    form: InputFormGenerator | None = None,
    assignee: Assignee | None = Assignee.SYSTEM,
    resume_auth_callback: Authorizer | None = None,
    retry_auth_callback: Authorizer | None = None,
) -> Step:
    step_func = cast(Step, f)

    step_func.name = name
    step_func.form = form
    step_func.assignee = assignee
    step_func.resume_auth_callback = resume_auth_callback
    step_func.retry_auth_callback = retry_auth_callback
    return step_func


class StepList(list[Step]):
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
    def __getitem__(self, i: int) -> Step: ...

    @overload
    def __getitem__(self, i: slice) -> StepList: ...

    def __getitem__(self, i: int | slice) -> Step | StepList:
        retval: Step | list[Step] = super().__getitem__(i)
        if isinstance(retval, list):
            # ensure we return a StepList and not a regular list.
            retval = type(self)(retval)
        return retval

    def __rshift__(self, other: StepList | Step) -> StepList:
        if isinstance(other, Step):
            return StepList([*self, other])

        if isinstance(other, StepList):
            return StepList([*self, *other])

        if hasattr(other, "__name__"):  # type: ignore
            raise ValueError(
                f"Expected @step decorated function or type Step or StepList, got {type(other)} with name {other.__name__} instead."
            )
        raise ValueError(f"Expected @step decorated function or type Step or StepList, got {type(other)} instead.")

    def __str__(self) -> str:
        return f"StepList [{', '.join(x.name for x in self)}]"

    def __repr__(self) -> str:
        return f"StepList [{', '.join(repr(x) for x in self)}]"


OnErrorHandler = Callable[[ErrorDict, State], StepList | None]
LoopBody = StepList | Callable[[State, int], StepList]


def _handle_simple_input_form_generator(f: StateInputStepFunc) -> StateInputFormGenerator:
    """Processes f into a form generator and injects a pre-hook for user authorization."""
    if inspect.isgeneratorfunction(f):
        return cast(StateInputFormGenerator, f)
    if inspect.isgenerator(f):
        raise ValueError("Got a generator object instead of function, this is not correct")

    # If f is a SimpleInputFormGenerator convert to new style generator function
    def form_generator(state: State) -> FormGenerator:
        user_input: FormPage = yield cast(StateSimpleInputFormGenerator, f)(state)
        return user_input.model_dump()

    return form_generator


async def allow(_: OIDCUserModel | None) -> bool:
    """Default function to return True in absence of user-defined authorize function."""
    return True


def default_user_inputs() -> list[State]:
    """Provide the default user inputs when executing a workflow when user inputs are not explicitly provided.

    This mirrors the requirement from make_workflow() to always have at least 1 form.
    """
    return [{}]


def make_workflow(
    f: Callable,
    description: str,
    initial_input_form: InputStepFunc | None,
    target: Target,
    steps: StepList,
    authorize_callback: Authorizer | None = None,
    retry_auth_callback: Authorizer | None = None,
    run_predicate: RunPredicate | None = None,
) -> Workflow:
    @functools.wraps(f)
    def wrapping_function() -> NoReturn:
        raise Exception("This function should not be executed")

    wf: Workflow = cast(Workflow, wrapping_function)

    wf.name = f.__name__  # default, will be changed by LazyWorkflowInstance
    wf.description = description
    wf.authorize_callback = allow if authorize_callback is None else authorize_callback
    # If no retry auth policy is given, defer to policy for process creation.
    wf.retry_auth_callback = wf.authorize_callback if retry_auth_callback is None else retry_auth_callback

    if initial_input_form is None:
        # We always need a form to prevent starting a workflow when no input is needed.
        # This would happen on first post that is used to retrieve the first form page
        initial_input_form = cast(InputStepFunc, const(FormPage))

    wf.initial_input_form = _handle_simple_input_form_generator(initial_input_form)
    wf.target = target
    wf.steps = steps
    wf.run_predicate = run_predicate

    wf.__doc__ = make_workflow_doc(wf)

    return wf


def step(
    name: str,
    retry_auth_callback: Authorizer | None = None,
) -> Callable[[StepFunc], Step]:
    """Mark a function as a workflow step."""

    def decorator(func: StepFunc) -> Step:
        @functools.wraps(func)
        def wrapper(state: State) -> Process:
            with bound_contextvars(
                func=func.__qualname__,
                workflow_name=state.get("workflow_name"),
                process_id=state.get("process_id"),
            ):
                step_in_inject_args = inject_args(func)
                try:
                    with transactional(db, logger):
                        result = step_in_inject_args(state)
                        return Success(result)
                except Exception as ex:
                    logger.warning("Step failed", exc_info=ex)
                    return Failed(ex)

        return make_step_function(
            wrapper,
            name,
            retry_auth_callback=retry_auth_callback,
        )

    return decorator


def retrystep(
    name: str,
    retry_auth_callback: Authorizer | None = None,
) -> Callable[[StepFunc], Step]:
    """Mark a function as a retryable workflow step.

    If this step fails it goes to `Waiting` were it will be retried periodically. If it `Success` it acts as a normal
    step.
    """

    def decorator(func: StepFunc) -> Step:
        @functools.wraps(func)
        def wrapper(state: State) -> Process:
            with bound_contextvars(
                func=func.__qualname__,
                workflow_name=state.get("workflow_name"),
                process_id=state.get("process_id"),
            ):
                step_in_inject_args = inject_args(func)
                try:
                    with transactional(db, logger):
                        result = step_in_inject_args(state)
                        return Success(result)
                except Exception as ex:
                    return Waiting(ex)

        return make_step_function(
            wrapper,
            name,
            retry_auth_callback=retry_auth_callback,
        )

    return decorator


def inputstep(
    name: str,
    assignee: Assignee,
    resume_auth_callback: Authorizer | None = None,
    retry_auth_callback: Authorizer | None = None,
) -> Callable[[InputStepFunc], Step]:
    """Add user input step to workflow.

    Any authorization callbacks will be attached to the resulting Step.

    IMPORTANT: In contrast to other workflow steps, the `@inputstep` wrapped function will not run in the
    workflow engine! This means that it must be free of side effects!

    Example::

        @inputstep("User step", assignee=Assignee.NOC)
        def user_step(state: State) -> FormGenerator:
            class Form(FormPage):
                name: str
            user_input = yield Form
            return {**user_input.model_dump(), "some extra key": True}

    """

    def decorator(func: InputStepFunc) -> Step:
        def wrapper(state: State) -> FormGenerator:
            form_generator_in_form_inject_args = form_inject_args(func)

            form_generator = _handle_simple_input_form_generator(form_generator_in_form_inject_args)

            return form_generator(state)

        @functools.wraps(func)
        def suspend(state: State) -> Process:
            return Suspend(state)

        return make_step_function(
            suspend,
            name,
            wrapper,
            assignee,
            resume_auth_callback=resume_auth_callback,
            retry_auth_callback=retry_auth_callback,
        )

    return decorator


def _extend_step_group_steps(name: str, steps: StepList) -> StepList:
    def add_sub_group_info_to_state() -> State:
        return {"__step_name_override": name, "__step_group": name}

    def remove_sub_group_info_from_state() -> State:
        return {"__remove_keys": ["__step_group", "__sub_step"]}

    enter_step = begin >> step(f"{name} - Enter")(add_sub_group_info_to_state)
    exit_step = step(f"{name} - Exit")(remove_sub_group_info_from_state)

    return enter_step >> steps >> exit_step


def step_group(
    name: str, steps: StepList, extract_form: bool = True, retry_auth_callback: Authorizer | None = None
) -> Step:
    """Add a group of steps to the workflow as a single step.

    A step group is a sequence of steps that act as a single step.
    Each step in the step group is a normal step on its own. So they are callables (State) -> Process.
    The state of the group will be the last state of the sub-steps. So if one of the steps goes to FAILED,
    the group goes to failed. If a step goes to SUSPEND, the group is in SUSPEND. If a step goes to SUCCESS however,
    the group is still RUNNING. It will be in SUCCESS only of all the sub-steps are in SUCCESS.

    Args:
        name: The name of the step
        steps: The sub steps in the step group
        extract_form: Whether to attach the first form of the sub steps to the step group
        retry_auth_callback: Callback to determine if user is authorized to retry this group on failure
    """

    steps = _extend_step_group_steps(name, steps)

    def func(initial_state: State) -> Process:
        step_log_fn = step_log_fn_var.get()

        # If sub_step information is present in the state. Resume from the next sub step
        if "__sub_step" in initial_state:
            step_list = StepList(dropwhile(lambda s: s.name != initial_state.get("__sub_step"), steps))[1:]
        else:
            step_list = steps

        def dblogstep(step_: Step, p: Process) -> Process:
            p = p.map(lambda s: s | {"__sub_step": step_.name, "__step_name_override": name})
            # If this is not the first step to be executed, replace previous state
            if step_list[0] != step_ or "__sub_step" in initial_state:
                p = p.map(lambda s: s | {"__replace_last_state": True})
            return step_log_fn(step_, p)

        step_group_start_time = nowtz().timestamp()
        process: Process = Success(initial_state)
        process = _exec_steps(step_list, process, dblogstep)
        # Add instruction to replace state of last sub step before returning process _exec_steps higher in the call tree
        return process.map(
            lambda s: s | {"__replace_last_state": True, "__last_step_started_at": step_group_start_time}
        )

    # Make sure we return a form is a sub step has a form
    form = next((sub_step.form for sub_step in steps if sub_step.form), None) if extract_form else None
    return make_step_function(func, name, form, retry_auth_callback=retry_auth_callback)


def _create_endpoint_step(key: str = DEFAULT_CALLBACK_ROUTE_KEY) -> StepFunc:
    def stepfunc(process_id: UUID) -> State:
        token = secrets.token_urlsafe()
        route = f"/api/processes/{process_id}/callback/{token}"
        # Also add the token under __callback_token for internal use
        return {key: route, CALLBACK_TOKEN_KEY: token}

    return stepfunc


def _awaitstep(name: str, result_key: str | None = None, timeout: int | None = None) -> Step:
    extra_state: State = {}
    if result_key:
        extra_state["__callback_result_key"] = result_key
    if timeout is not None:
        extra_state[CALLBACK_TIMEOUT_KEY] = timeout

    def await_(state: State) -> Process:
        return AwaitingCallback(state | extra_state)

    return make_step_function(await_, name)


def callback_step(
    name: str,
    action_step: Step,
    validate_step: Step,
    result_key: str | None = None,
    callback_route_key: str = DEFAULT_CALLBACK_ROUTE_KEY,
    timeout: int | None = None,
) -> Step:
    """Creates an asynchronous callback step.

    Internally creates a step group with the following sub steps:

    - Action - This performs the required side effect to an external system. After this, an endpoint is generated and
    stored with the process and the process goes into AWAITING_CALLBACK state.
    - Validate - Uses the provided validate_fn to validate the data coming from the external system.

    The data returned in the callback will be merged in the state. An optional result_key parameter can be supplied
    to specify under which key the data will be merged.

    By default the process waits indefinitely for the callback. When ``timeout`` (in seconds) is supplied, a process
    still in AWAITING_CALLBACK after that many seconds (measured from when the await started) is transitioned to FAILED
    by the ``task_validate_awaiting_callbacks`` scheduled task, so it can be retried or aborted through the normal
    flows. The timeout is a minimum: enforcement resolution equals that task's run interval (30 seconds by default).
    """
    create_endpoint_step = step(f"{name} - Create endpoint")(_create_endpoint_step(key=callback_route_key))
    await_step = _awaitstep(f"{name} - Await callback", result_key=result_key, timeout=timeout)
    cleanup_step = step(f"{name} - Cleanup callback step")(lambda: {"__remove_keys": [CALLBACK_TOKEN_KEY]})
    return step_group(
        name=name, steps=begin >> create_endpoint_step >> action_step >> await_step >> validate_step >> cleanup_step
    )


def _purestep(name: str) -> Callable[[StepToProcessFunc], StepList]:
    """Part of workflow "DSL" to map a `state -> Process state` function into a workflow step."""

    def _purestep(f: StepToProcessFunc) -> StepList:
        return StepList([make_step_function(f, name)])

    return _purestep


def conditional(p: Callable[[State], bool]) -> Callable[..., StepList]:
    """Use a predicate to conditionally skip workflow steps at runtime.

    When the predicate `p` returns `True` for the current workflow state,
    the wrapped step(s) execute normally. When it returns `False`, each
    wrapped step returns `Skipped` — the step is recorded but does not
    modify the state or halt the workflow.

    Can wrap a single step or multiple steps (via a `StepList`). When
    wrapping multiple steps the predicate is evaluated independently for
    each step.
    """

    def _conditional(steps_or_func: StepList | Step) -> StepList:
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
            return result.map(set(state))

        return make_step_function(wrapper, step.name, step.form, step.assignee)

    return wrap


def focussteps(key: str) -> Callable[[Step | StepList], StepList]:
    """Return a function that maps `steplens` over `steps`, getting and setting a single key."""

    def zoom(steps_or_func: Step | StepList) -> StepList:
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


def _warn_description_deprecated() -> None:
    """Emit a deprecation warning when a workflow decorator `description` parameter is used."""
    warnings.warn(
        "The 'description' parameter in workflow decorators is deprecated. "
        "Workflow descriptions should be managed in the database via the UI or API endpoint. "
        "Please remove the 'description' parameter from your decorator.",
        DeprecationWarning,
        stacklevel=3,
    )
    logger.warning(
        "Workflow decorator description is deprecated",
        hint="Remove the description parameter and manage it via database/UI instead",
    )


def workflow(
    description: str = "",
    initial_input_form: InputStepFunc | None = None,
    target: Target = Target.SYSTEM,
    authorize_callback: Authorizer | None = None,
    retry_auth_callback: Authorizer | None = None,
    run_predicate: RunPredicate | None = None,
) -> Callable[[Callable[[], StepList]], Workflow]:
    """Transform an initial_input_form and a step list into a workflow.

    Use this for other workflows. For create workflows use :func:`create_workflow`

    .. deprecated::
        The `description` parameter is deprecated and will be removed in a future version.
        Workflow descriptions should now be managed in the database via the UI or API endpoint.
        You can safely remove this parameter from the decorator.
        Removal is tracked in issue #1463.

    Example::

        @workflow()
        def create_service_port():
            init
            << do_something
            << done
    """
    if description:
        _warn_description_deprecated()
    if initial_input_form is None:
        initial_input_form_in_form_inject_args = None
    else:
        initial_input_form_in_form_inject_args = form_inject_args(initial_input_form)

    def _workflow(f: Callable[[], StepList]) -> Workflow:
        return make_workflow(
            f,
            description,
            initial_input_form_in_form_inject_args,
            target,
            f(),
            authorize_callback=authorize_callback,
            retry_auth_callback=retry_auth_callback,
            run_predicate=run_predicate,
        )

    return _workflow


@dataclass
class ProcessStat:
    process_id: UUID
    workflow: Workflow
    state: Process
    log: StepList  # Remaining steps to execute
    current_user: str
    user_model: OIDCUserModel | None = None

    def update(self, **vs: Any) -> ProcessStat:
        """Update ProcessStat.

        >>> pstat = ProcessStat('', None, {}, [], "")
        >>> pstat.update(state={"a": "b"})
        ProcessStat(process_id='', workflow=None, state={'a': 'b'}, log=[], current_user='', user_model=None)
        """
        return ProcessStat(**{**asdict(self), **vs})


S = TypeVar("S")
F = TypeVar("F")


@strawberry.enum
class ProcessStatus(strEnum):
    CREATED = "created"
    RUNNING = "running"
    SUSPENDED = "suspended"
    WAITING = "waiting"
    AWAITING_CALLBACK = "awaiting_callback"
    ABORTED = "aborted"
    FAILED = "failed"
    API_UNAVAILABLE = "api_unavailable"
    INCONSISTENT_DATA = "inconsistent_data"
    COMPLETED = "completed"
    RESUMED = "resumed"


class StepStatus(strEnum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    SUSPEND = "suspend"
    WAITING = "waiting"
    AWAITING_CALLBACK = "awaiting_callback"
    FAILED = "failed"
    ABORT = "abort"
    COMPLETE = "complete"


class Process(Generic[S]):
    """ADT base class.

    This class defines an Algebraic Data Type - specifically a "sum type" - that defines the possible
    variants of a Process. It encapsulates the state and allows to fold _instances_ of a process into
    a single value. These instances correspond to subsequent steps of the process.
    """

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

        >>> AwaitingCallback(1).map(inc)
        AwaitingCallback 2

        >>> Abort(1).map(inc)
        Abort 2

        >>> Failed(1).map(inc)
        Failed 2

        >>> Complete(1).map(inc)
        Complete 2
        """

        def g(x: S) -> Process[S]:
            self_ = self.__class__
            return self_(f(x))

        return self._fold(g, g, g, g, g, g, g, g)

    def _fold(
        self,
        success: Callable[[S], F],
        skipped: Callable[[S], F],
        suspend: Callable[[S], F],
        waiting: Callable[[S], F],
        awaiting_callback: Callable[[S], F],
        abort: Callable[[S], F],
        failed: Callable[[S], F],
        complete: Callable[[S], F],
    ) -> F:
        """Unwrap the state from the Process category.

        >>> Success('a')._fold(Success, Skipped, Suspend, Waiting, AwaitingCallback, Abort, Failed, Complete)
        Success 'a'

        >>> Skipped('a')._fold(Success, Skipped, Suspend, Waiting, AwaitingCallback, Abort, Failed, Complete)
        Skipped 'a'

        >>> Suspend('a')._fold(Success, Skipped, Suspend, Waiting, AwaitingCallback, Abort, Failed, Complete)
        Suspend 'a'

        >>> Waiting('a')._fold(Success, Skipped, Suspend, Waiting, AwaitingCallback, Abort, Failed, Complete)
        Waiting 'a'

        >>> AwaitingCallback('a')._fold(Success, Skipped, Suspend, Waiting, AwaitingCallback, Abort, Failed, Complete)
        AwaitingCallback 'a'

        >>> Abort('a')._fold(Success, Skipped, Suspend, Waiting, AwaitingCallback, Abort, Failed, Complete)
        Abort 'a'

        >>> Failed('a')._fold(Success, Skipped, Suspend, Waiting, AwaitingCallback, Abort, Failed, Complete)
        Failed 'a'

        >>> Complete('a')._fold(Success, Skipped, Suspend, Waiting, AwaitingCallback, Abort, Failed, Complete)
        Complete 'a'

        >>> Process('a')._fold(Success, Skipped, Suspend, Waiting, AwaitingCallback, Abort, Failed, Complete)
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

        >>> AwaitingCallback('a').unwrap()
        'a'

        >>> Abort('a').unwrap()
        'a'

        >>> Failed('a').unwrap()
        'a'

        >>> Complete('a').unwrap()
        'a'
        """
        return self._fold(identity, identity, identity, identity, identity, identity, identity, identity)

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

        >>> AwaitingCallback('a').issuccess()
        False

        >>> Abort('a').issuccess()
        False

        >>> Failed('a').issuccess()
        False

        >>> Complete('a').issuccess()
        False
        """
        return self._fold(
            const(True),
            const(False),
            const(False),
            const(False),
            const(False),
            const(False),
            const(False),
            const(False),
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

        >>> AwaitingCallback('a').isskipped()
        False

        >>> Abort('a').isskipped()
        False

        >>> Failed('a').isskipped()
        False

        >>> Complete('a').isskipped()
        False
        """
        return self._fold(
            const(False),
            const(True),
            const(False),
            const(False),
            const(False),
            const(False),
            const(False),
            const(False),
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

        >>> AwaitingCallback('a').issuspend()
        False

        >>> Abort('a').issuspend()
        False

        >>> Failed('a').issuspend()
        False

        >>> Complete('a').issuspend()
        False
        """
        return self._fold(
            const(False),
            const(False),
            const(True),
            const(False),
            const(False),
            const(False),
            const(False),
            const(False),
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

        >>> AwaitingCallback('a').iswaiting()
        False

        >>> Abort('a').iswaiting()
        False

        >>> Failed('a').iswaiting()
        False

        >>> Complete('a').iswaiting()
        False
        """
        return self._fold(
            const(False),
            const(False),
            const(False),
            const(True),
            const(False),
            const(False),
            const(False),
            const(False),
        )

    def isawaitingcallback(self) -> bool:
        """Test if this instance is AwaitingCallback.

        >>> Success('a').isawaitingcallback()
        False

        >>> Skipped('a').isawaitingcallback()
        False

        >>> Suspend('a').isawaitingcallback()
        False

        >>> Waiting('a').isawaitingcallback()
        False

        >>> AwaitingCallback('a').isawaitingcallback()
        True

        >>> Abort('a').isawaitingcallback()
        False

        >>> Failed('a').isawaitingcallback()
        False

        >>> Complete('a').isawaitingcallback()
        False
        """
        return self._fold(
            const(False),
            const(False),
            const(False),
            const(False),
            const(True),
            const(False),
            const(False),
            const(False),
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

        >>> AwaitingCallback('a').isabort()
        False

        >>> Abort('a').isabort()
        True

        >>> Failed('a').isabort()
        False

        >>> Complete('a').isabort()
        False
        """
        return self._fold(
            const(False),
            const(False),
            const(False),
            const(False),
            const(False),
            const(True),
            const(False),
            const(False),
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

        >>> AwaitingCallback('a').isfailed()
        False

        >>> Abort('a').isfailed()
        False

        >>> Failed('a').isfailed()
        True

        >>> Complete('a').isfailed()
        False
        """
        return self._fold(
            const(False),
            const(False),
            const(False),
            const(False),
            const(False),
            const(False),
            const(True),
            const(False),
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

        >>> AwaitingCallback('a').iscomplete()
        False

        >>> Abort('a').iscomplete()
        False

        >>> Failed('a').iscomplete()
        False

        >>> Complete('a').iscomplete()
        True
        """
        return self._fold(
            const(False),
            const(False),
            const(False),
            const(False),
            const(False),
            const(False),
            const(False),
            const(True),
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

        >>> Success('a') != AwaitingCallback('a')
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

        >>> AwaitingCallback({}).status
        <StepStatus.AWAITING_CALLBACK: 'awaiting_callback'>

        >>> Abort({}).status
        <StepStatus.ABORT: 'abort'>

        >>> Failed({}).status
        <StepStatus.FAILED: 'failed'>

        >>> Complete({}).status
        <StepStatus.COMPLETE: 'complete'>
        """
        ss = getattr(self, "__name__", self.__class__.__name__).upper()
        return StepStatus[ss]

    @staticmethod
    def from_status(status: StepStatus, state: S) -> Process | None:
        """Make Process based on status and state.

        >>> Process.from_status('success', {})
        Success {}

        >>> Process.from_status('skipped', {})
        Skipped {}

        >>> Process.from_status('suspend', {})
        Suspend {}

        >>> Process.from_status('waiting', {})
        Waiting {}

        >>> Process.from_status('awaiting_callback', {})
        AwaitingCallback {}

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

        >>> AwaitingCallback({}).overall_status
        <ProcessStatus.AWAITING_CALLBACK: 'awaiting_callback'>

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
            const(ProcessStatus.AWAITING_CALLBACK),
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

        >>> repr(AwaitingCallback({}))
        'AwaitingCallback {}'

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

    def on_awaiting_callback(self, f: Callable[[S], S]) -> Process[S]:
        """Apply function on Process state only when AwaitingCallback."""
        return self.map(f) if self.isawaitingcallback() else self

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
        """Execute a step transition based on a step function.

        A step can only be executed if the current state is success or skipped.

        >>> Success({"a":1}).execute_step(lambda s: Success(s))
        Success {'a': 1}
        >>> Success({"a":1}).execute_step(lambda s: Failed(s))
        Failed {'a': 1}

        >>> Waiting({"a":1}).execute_step(lambda s: Failed(s))
        Waiting {'a': 1}

        """

        return self._fold(step, step, Suspend, Waiting, AwaitingCallback, Abort, Failed, Complete)

    def abort(self) -> Process[S]:
        """Abort process.

        Always works except for completed processes
        """
        return self._fold(Abort, Abort, Abort, Abort, Abort, Abort, Abort, Complete)

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

        next_state = self._fold(Success, Success, Success, Success, Success, Abort, Success, Complete)
        if self.issuspend() or self.isawaitingcallback():
            return resume_suspend(next_state)  # type: ignore

        return next_state  # type: ignore


class Success(Process[S]):
    def _fold(
        self,
        success: Callable[[S], F],
        skipped: Callable[[S], F],
        suspend: Callable[[S], F],
        waiting: Callable[[S], F],
        awaiting_callback: Callable[[S], F],
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
        awaiting_callback: Callable[[S], F],
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
        awaiting_callback: Callable[[S], F],
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
        awaiting_callback: Callable[[S], F],
        abort: Callable[[S], F],
        failed: Callable[[S], F],
        complete: Callable[[S], F],
    ) -> F:
        return waiting(self.s)


class AwaitingCallback(Process[S]):
    __name__ = "Awaiting_Callback"

    def _fold(
        self,
        success: Callable[[S], F],
        skipped: Callable[[S], F],
        suspend: Callable[[S], F],
        waiting: Callable[[S], F],
        awaiting_callback: Callable[[S], F],
        abort: Callable[[S], F],
        failed: Callable[[S], F],
        complete: Callable[[S], F],
    ) -> F:
        return awaiting_callback(self.s)


class Abort(Process[S]):
    def _fold(
        self,
        success: Callable[[S], F],
        skipped: Callable[[S], F],
        suspend: Callable[[S], F],
        waiting: Callable[[S], F],
        awaiting_callback: Callable[[S], F],
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
        awaiting_callback: Callable[[S], F],
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
        awaiting_callback: Callable[[S], F],
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
    StepStatus.AWAITING_CALLBACK: AwaitingCallback,
    StepStatus.ABORT: Abort,
    StepStatus.FAILED: Failed,
    StepStatus.COMPLETE: Complete,
}

_NUM_STATUSES = len(_STATUSES)


def cond_bind(log: BoundLogger, state: dict[str, Any], key: str, as_key: str | None = None) -> BoundLogger:
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


def log_workflow_failure(error: ErrorDict) -> None:
    """Log the error state from a failed workflow."""
    logger.info("Workflow returned an error.", **error)


def invalidate_status_counts() -> None:
    """Broadcast invalidate status counts to the websocket."""
    from orchestrator.core.websocket import broadcast_invalidate_status_counts

    broadcast_invalidate_status_counts()


def capture_workflow_failure(err: Any) -> None:
    """Capture the exception from a failed workflow.

    This may provide useful insights into application or infra errors.
    However, this may also cause sentry issues for exceptions that are "business as usual".
    In that case, you can pass a function `app.add_sentry(before_send=before_send)` in which you can evaluate
    exceptions and prevent sending them to sentry.
    https://docs.sentry.io/platforms/python/configuration/filtering/
    """
    match err:
        case Exception() if app_settings.TRACING_ENABLED:
            import sentry_sdk

            sentry_sdk.capture_exception(err)
        case _:
            pass


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
            with transactional(db, logger):
                engine_status = get_engine_settings_table()
                if engine_status.global_lock:
                    # Exiting from thread workflow engine is Paused or Pausing
                    consolelogger.info(
                        "Not executing Step as the workflow engine is Paused. Process will remain in state 'running'"
                    )
                    return process

            process = process.map(lambda s: s | {"__last_step_started_at": nowtz().timestamp()})
            step_result_process = process.execute_step(step)
        except Exception as e:
            consolelogger.error("An exception occurred while executing the workflow step.", exc_info=e)
            step_result_process = Failed(e)

        # write the new process state after the step execution to the database
        # Convert ErrorState to ErrorDict when Failed or Waiting before writing to the database
        # as bare exceptions are not JSON serializable
        result_to_log = step_result_process.on_failed(error_state_to_dict).on_waiting(error_state_to_dict)
        result_to_log.on_success(mutationlogger).on_failed(log_workflow_failure).on_waiting(log_workflow_failure)

        # Capture the original exception that caused the workflow to fail
        step_result_process.on_failed(capture_workflow_failure)

        with transactional(db, logger):
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
        state = process.unwrap()
        if "__step_group" in state:
            step = steps[0]
        else:
            step = steps.pop(0)
        return _logstep(step, process)

    next_state = pstat.state.resume(resume_suspend)
    # Set the step_log_fn in the contextvar.
    # This enables recursive step execution of sub steps with the same StepLogFunc.
    # Should probably be refactored at some point as contextvars is a kind of global state.
    step_log_fn_var.set(_logstep)
    executed_steps = _exec_steps(steps, next_state, _logstep)
    if executed_steps.overall_status == ProcessStatus.FAILED:
        invalidate_status_counts()
    return executed_steps


def abort_wf(pstat: ProcessStat, logstep: StepLogFunc) -> Process:
    """Abort a suspended workflow."""

    if not pstat.state.iscomplete():
        abort_func = make_step_function(Abort, "User Aborted")

        state = pstat.state.abort()

        with transactional(db, logger):
            return logstep(pstat, abort_func, state)
    return pstat.state


def fail_awaiting_wf(pstat: ProcessStat, logstep: StepLogFunc, reason: str = "Callback timed out") -> Process:
    """Fail a workflow that is stuck awaiting a callback.

    Overwrites the existing AWAITING_CALLBACK step in place (via ``__replace_last_state``) and turns it into FAILED, so
    the process can be retried or aborted through the normal flows. The ``isawaitingcallback`` guard makes this a no-op
    when the callback has arrived in the meantime, which also protects against the callback-arrives-during-sweep race.
    """
    if not pstat.state.isawaitingcallback():
        return pstat.state

    fail_func = make_step_function(Failed, reason)
    state = Failed({**pstat.state.unwrap(), "error": reason, "__replace_last_state": True})

    with transactional(db, logger):
        return logstep(pstat, fail_func, state)


# The synthetic status of a `loop_steps` entry that has been queued but not yet executed. Not a
# `StepStatus` member: no `Process` variant is ever "pending", this is `loop`'s own bookkeeping.
LOOP_STEP_PENDING: Literal["pending"] = "pending"
LoopStepStatus = StepStatus | Literal["pending"]


class LoopLimitReached(Exception):  # noqa: N818
    """Raised by :func:`loop` when its iteration cap is reached without the exit predicate firing."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"Loop iteration limit of {limit} reached without completing")
        self.limit = limit


@dataclass(frozen=True)
class LoopStepEntry:
    """A single row in `loop_steps`, mirroring the shape of a process's own step log."""

    name: str
    status: LoopStepStatus
    state: dict[str, Any] | None = None
    started: str | None = None
    completed: str | None = None
    was_suspended: bool = False
    _suspend_baseline: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if not (k == "_suspend_baseline" and v is None)}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> LoopStepEntry:
        return LoopStepEntry(**d)


@dataclass(frozen=True)
class LoopStepsBodyDescriptor:
    """Body-descriptor variant recording that a stretch of `step_<iteration>_*` positions came from `steps`."""

    iteration: int
    source: Literal["steps"] = "steps"


@dataclass(frozen=True)
class LoopOnErrorBodyDescriptor:
    """Body-descriptor variant: a stretch of positions produced by an `on_error` handler."""

    error: ErrorDict
    iteration_start_state: dict[str, Any]
    source: Literal["on_error"] = "on_error"


LoopBodyDescriptor = LoopStepsBodyDescriptor | LoopOnErrorBodyDescriptor


def _loop_body_descriptor_from_dict(d: dict[str, Any]) -> LoopBodyDescriptor:
    if d["source"] == "on_error":
        return LoopOnErrorBodyDescriptor(error=d["error"], iteration_start_state=d["iteration_start_state"])
    return LoopStepsBodyDescriptor(iteration=d["iteration"])


def _loop_next_position(loop_steps: list[dict[str, Any]], iteration: int) -> int:
    """First free position index within `iteration`."""
    prefix = f"step_{iteration}_"
    return sum(1 for entry in loop_steps if entry.get("name", "").startswith(prefix))


def _loop_seed_pending_entries(
    s: State,
    raw_steps: StepList,
    iteration: int,
    body_descriptor: LoopBodyDescriptor,
) -> tuple[State, int]:
    """Append pending `loop_steps` entries for `raw_steps`; returns the new state and base position."""
    existing = list(s.get(LOOP_STEPS_KEY, []))
    # Continue numbering after this iteration's existing entries, so an on_error recovery doesn't
    # collide with the trunk it's replacing the tail of.
    base = _loop_next_position(existing, iteration)
    pending = [
        LoopStepEntry(name=f"step_{iteration}_{base + position}", status=LOOP_STEP_PENDING).to_dict()
        for position in range(len(raw_steps))
    ]
    bodies = dict(s.get(LOOP_STEPS_BODIES_KEY, {}))
    bodies[f"{iteration}:{base}"] = asdict(body_descriptor)
    new_state = s | {LOOP_STEPS_KEY: existing + pending, LOOP_STEPS_BODIES_KEY: bodies}
    return new_state, base


def _loop_flip_resumed_entry(s: State, resumed_name: str, ambient: State) -> State:
    """Flip the resumed sub-step's `loop_steps` entry from `suspend` to `success`."""
    entries = list(s.get(LOOP_STEPS_KEY, []))

    stored_baseline: dict[str, Any] | None = None
    for raw_entry in entries:
        if raw_entry.get("name") == resumed_name and raw_entry.get("status") == StepStatus.SUSPEND:
            stored_baseline = raw_entry.get("_suspend_baseline")
            break

    if stored_baseline is not None:
        baseline = stored_baseline
    else:
        # No snapshot on the entry (shouldn't normally happen): fall back to ambient state plus
        # every prior entry's own delta, replaying what the baseline would have accumulated to.
        baseline = dict(ambient)
        for raw_entry in entries:
            baseline = {**baseline, **(raw_entry.get("state") or {})}
            if raw_entry.get("name") == resumed_name:
                break

    # The user's form input was merged into `s` between suspend and resume; diff against the
    # baseline to capture just the keys this submission added or changed.
    form_delta = _loop_entry_state_delta(baseline, s)

    for index, raw_entry in enumerate(entries):
        if raw_entry.get("name") == resumed_name and raw_entry.get("status") == StepStatus.SUSPEND:
            entry = LoopStepEntry.from_dict(raw_entry)
            merged_state = {**(entry.state or {}), **form_delta}
            new_entry = replace(
                entry,
                status=StepStatus.SUCCESS,
                state=merged_state,
                completed=nowtz().isoformat(),
                _suspend_baseline=None,
            )
            entries[index] = new_entry.to_dict()
            break
    return s | {LOOP_STEPS_KEY: entries}


def _loop_record_entry(s: State, step_name: str, status: StepStatus, before: State, error: ErrorDict | None) -> State:
    """Update (or seed) `step_name`'s `loop_steps` entry with the outcome of executing it."""
    delta = _loop_entry_state_delta(before, s)
    entries = list(s.get(LOOP_STEPS_KEY, []))
    for index, raw_entry in enumerate(entries):
        if raw_entry.get("name") != step_name:
            continue
        entry = LoopStepEntry.from_dict(raw_entry)
        merged_state = {**(entry.state or {}), **delta}
        new_entry = replace(
            entry,
            status=status,
            state=merged_state,
            started=entry.started or nowtz().isoformat(),
            completed=nowtz().isoformat(),
        )
        if status == StepStatus.SUSPEND:
            # Permanent structural fact about this entry's history, so it must live as a sibling of
            # `state` rather than inside it: `state` is reserved for what the step itself returned,
            # mirroring how the top-level process log keeps bookkeeping (started/completed/status)
            # separate from step output.
            new_entry = replace(new_entry, was_suspended=True, _suspend_baseline=_loop_strip_for_snapshot(before))
        if error is not None:
            new_entry = replace(new_entry, state={**merged_state, "error": error})
        entries[index] = new_entry.to_dict()
        break
    return s | {LOOP_STEPS_KEY: entries}


def _loop_run_steps(
    step_log_fn: StepLogFuncInternal,
    group_name: str,
    in_state: State,
    raw_steps: StepList,
    iteration: int,
    position_base: int,
    resume_cursor: str | None,
    continuation: bool,
) -> tuple[Process, State]:
    """Namespace, wrap, and execute `raw_steps` as (the rest of) an iteration.

    Returns the final `Process` together with the latest successfully-logged merged state, even
    when the `Process` itself is `Failed` (which carries an error dict, not state). The caller
    needs that merged state to recover `loop_steps` with the failing entry marked.
    """
    # Names of the iteration's own steps, as distinct from the Enter/Exit plumbing steps
    # `_extend_step_group_steps` adds below: those never get a `loop_steps` entry.
    iteration_step_names = {f"step_{iteration}_{position_base + position}" for position in range(len(raw_steps))}

    prefixed: StepList = StepList([])
    for position, raw_step in enumerate(raw_steps):
        renamed = make_step_function(
            raw_step, f"step_{iteration}_{position_base + position}", raw_step.form, raw_step.assignee
        )
        prefixed = prefixed >> renamed

    body = _extend_step_group_steps(f"{group_name}_{iteration}", prefixed)

    if resume_cursor is not None:
        # Resuming past a suspend: drop everything up to and including the step that suspended.
        step_list = StepList(dropwhile(lambda s: s.name != resume_cursor, body))[1:]
    else:
        step_list = body

    # `continuation` is True for steps that aren't the first ever executed for this `loop` step
    # invocation (a later iteration, or steps returned by an `on_error` handler); like resuming,
    # their first step must replace the prior terminal row rather than append a new one.
    force_replace = resume_cursor is not None or continuation
    committed_state: dict[str, State] = {"value": in_state}

    def dblogstep(step_: Step, p: Process) -> Process:
        p = p.map(lambda s: s | {"__sub_step": step_.name, "__step_name_override": group_name})
        if step_list[0] != step_ or force_replace:
            p = p.map(lambda s: s | {"__replace_last_state": True})

        if step_.name not in iteration_step_names:
            if p.issuccess() or p.isskipped():
                committed_state["value"] = p.unwrap()
            return step_log_fn(step_, p)

        status = p.status
        before = committed_state["value"]

        if p.issuccess() or p.isskipped() or p.issuspend():
            p = p.map(lambda s: _loop_record_entry(s, step_.name, status, before, None))
            committed_state["value"] = p.unwrap()
        else:
            committed_state["value"] = _loop_record_entry(
                committed_state["value"], step_.name, status, before, error_state_to_dict(p.unwrap())
            )

        return step_log_fn(step_, p)

    process: Process = Success(in_state)
    process = _exec_steps(step_list, process, dblogstep)
    return process, committed_state["value"]


def _loop_strip_for_snapshot(state: State) -> State:
    """Strip internal and array-bookkeeping keys before stashing a state snapshot inline."""
    return {
        k: v for k, v in state.items() if not k.startswith("__") and k not in (LOOP_STEPS_KEY, LOOP_STEPS_BRANCHES_KEY)
    }


def _loop_entry_state_delta(before: State, after: State) -> State:
    """The per-step delta to embed in a loop_steps entry's `state` field."""
    # Only keys the step actually changed or added, excluding internal `__`-prefixed keys and the
    # loop_steps/loop_steps_branches arrays themselves (embedding those would nest the whole
    # history inside every entry).
    return {
        k: v
        for k, v in after.items()
        if not k.startswith("__") and k not in (LOOP_STEPS_KEY, LOOP_STEPS_BRANCHES_KEY) and before.get(k) != v
    }


def _loop_derive_iteration(state: State, loop_name: str) -> int:
    """Derive the current iteration index from observable state.

    Sources, in priority order:

    1. `__step_group` (`<loop_name>_<iteration>`). Set while mid-step-group at suspend/resume time.
    2. The highest iteration seen in `loop_steps` entry names (`step_<iteration>_<position>`).
    3. 0. First iteration of a fresh run.
    """
    step_group_name = state.get(LOOP_STEP_GROUP_KEY, "") or ""
    prefix = f"{loop_name}_"
    if step_group_name.startswith(prefix):
        try:
            return int(step_group_name[len(prefix) :])
        except ValueError:
            pass

    max_iteration = -1
    for entry in state.get(LOOP_STEPS_KEY, []):
        name = entry.get("name", "")
        if name.startswith("step_"):
            parts = name.split("_")
            if len(parts) >= 3:
                try:
                    max_iteration = max(max_iteration, int(parts[1]))
                except ValueError:
                    pass
    return max_iteration if max_iteration >= 0 else 0


def _loop_build_steps(steps: LoopBody, state: State, iteration: int) -> StepList:
    if callable(steps) and not isinstance(steps, StepList):
        return steps(state, iteration)
    return steps


def _loop_resolve_body(
    steps: LoopBody, on_error: OnErrorHandler | None, descriptor: LoopBodyDescriptor, state: State
) -> StepList:
    if isinstance(descriptor, LoopStepsBodyDescriptor):
        return _loop_build_steps(steps, state, descriptor.iteration)
    if on_error is not None:
        replacement = on_error(descriptor.error, descriptor.iteration_start_state)
        return replacement if replacement is not None else StepList([])
    return StepList([])


def _loop_resolve_sub_step(steps: LoopBody, on_error: OnErrorHandler | None, name: str, state: State) -> Step | None:
    """Find the raw step function responsible for the currently suspended sub-step."""
    # Looks up the body-descriptor recorded when this stretch of positions was seeded (in
    # loop_steps_bodies) rather than rebuilding the whole iteration and counting positions, since an
    # on_error handler may have spliced a differently shaped set of steps into the middle of it.
    sub_step_name = state.get(LOOP_SUB_STEP_KEY)
    if not sub_step_name:
        return None
    iteration = _loop_derive_iteration(state, name)

    prefix = f"step_{iteration}_"
    if not sub_step_name.startswith(prefix):
        return None
    try:
        target_position = int(sub_step_name[len(prefix) :])
    except ValueError:
        return None

    bodies: dict[str, dict[str, Any]] = state.get(LOOP_STEPS_BODIES_KEY, {})
    candidates = [
        (int(key.split(":", 1)[1]), raw_descriptor)
        for key, raw_descriptor in bodies.items()
        if key.startswith(f"{iteration}:") and int(key.split(":", 1)[1]) <= target_position
    ]
    if not candidates:
        return None
    base, raw_descriptor = max(candidates, key=lambda candidate: candidate[0])
    descriptor = _loop_body_descriptor_from_dict(raw_descriptor)

    raw_steps = _loop_resolve_body(steps, on_error, descriptor, state)
    position = target_position - base
    if 0 <= position < len(raw_steps):
        return raw_steps[position]
    return None


def _loop_start_iteration(
    steps: LoopBody, name: str, state: State, initial_state: State, iteration: int
) -> tuple[State, StepList, int, str | None]:
    """Prepare the current iteration's steps, seeding or locating its `loop_steps` entries.

    Returns the (possibly updated) state, the iteration's raw step list, the position base for
    naming its sub-steps, and a resume cursor (the suspended sub-step's name) if we're resuming
    mid-iteration rather than starting it fresh.
    """
    current_steps = _loop_build_steps(steps, state, iteration)

    resuming_mid_iteration = LOOP_SUB_STEP_KEY in state and state.get(LOOP_STEP_GROUP_KEY, "").startswith(
        f"{name}_{iteration}"
    )
    if not resuming_mid_iteration:
        state, position_base = _loop_seed_pending_entries(
            state, current_steps, iteration, body_descriptor=LoopStepsBodyDescriptor(iteration=iteration)
        )
        return state, current_steps, position_base, None

    state = _loop_flip_resumed_entry(state, state[LOOP_SUB_STEP_KEY], initial_state)
    resume_cursor = state[LOOP_SUB_STEP_KEY]
    # Entries for `current_steps` already exist, one per step; their base position is the count of
    # this iteration's existing entries minus the count of steps in `current_steps` itself.
    existing = state.get(LOOP_STEPS_KEY, [])
    prefix = f"step_{iteration}_"
    position_base = sum(1 for entry in existing if entry.get("name", "").startswith(prefix)) - len(current_steps)
    return state, current_steps, position_base, resume_cursor


def _loop_recover_from_failure(
    on_error: OnErrorHandler | None,
    step_log_fn: StepLogFuncInternal,
    name: str,
    iteration: int,
    iteration_start_state: State,
    process: Process,
    last_committed: State,
) -> tuple[Process, State]:
    """Run `on_error` handlers until one recovers the iteration or gives up.

    Cuts the entries the failed attempt queued or executed out of `loop_steps` into
    `loop_steps_branches`, then seeds and runs the handler's replacement steps in their place.
    """
    while process.isfailed() and on_error is not None:
        try:
            recovered_steps = on_error(cast(ErrorDict, process.unwrap()), iteration_start_state)
        except Exception as ex:
            # Mirror @step's own exception handling: a raising on_error is a bug in the handler, not
            # a deliberate signal. Log it and propagate the original failure that on_error was asked
            # to handle, rather than replacing it with the handler's own exception -- the same
            # outcome as on_error returning None.
            logger.warning("on_error handler failed", exc_info=ex)
            break
        if recovered_steps is None:
            break

        failed_loop_steps = [LoopStepEntry.from_dict(raw_entry) for raw_entry in last_committed.get(LOOP_STEPS_KEY, [])]
        failed_index = next(
            (index for index, entry in enumerate(failed_loop_steps) if entry.status == StepStatus.FAILED), None
        )
        if failed_index is None:
            # Defensive fallback (every step gets an entry, so this shouldn't happen): cut at the
            # first still-pending entry instead of the log's length, so unrun entries move to
            # loop_steps_branches instead of staying dangling in the trunk.
            failed_index = next(
                (index for index, entry in enumerate(failed_loop_steps) if entry.status == LOOP_STEP_PENDING),
                len(failed_loop_steps),
            )

        abandoned = failed_loop_steps[failed_index:]
        trunk = failed_loop_steps[:failed_index]

        recovery_state = iteration_start_state | {LOOP_STEPS_KEY: [entry.to_dict() for entry in trunk]}
        if abandoned:
            branches = dict(last_committed.get(LOOP_STEPS_BRANCHES_KEY, {}))
            branches[str(failed_index)] = [entry.to_dict() for entry in abandoned]
            recovery_state = recovery_state | {LOOP_STEPS_BRANCHES_KEY: branches}

        recovery_state, recovery_position_base = _loop_seed_pending_entries(
            recovery_state,
            recovered_steps,
            iteration,
            body_descriptor=LoopOnErrorBodyDescriptor(
                error=cast(ErrorDict, process.unwrap()),
                iteration_start_state=_loop_strip_for_snapshot(iteration_start_state),
            ),
        )
        process, last_committed = _loop_run_steps(
            step_log_fn,
            name,
            recovery_state,
            recovered_steps,
            iteration,
            recovery_position_base,
            None,
            continuation=True,
        )
    return process, last_committed


def loop(
    name: str,
    steps: LoopBody,
    *,
    until: Callable[[State], bool],
    limit: int = 100,
    on_error: OnErrorHandler | None = None,
) -> Step:
    """Add a repeating group of steps to the workflow as a single step.

    A loop is `step_group`'s repeating counterpart: the given steps run over and over, checking
    `until` before each iteration, until it returns `True` or `limit` iterations are reached. It only
    suspends when a step inside the current iteration suspends; it never suspends just to move from
    one iteration to the next. `loop` writes its own progress to `loop_steps` (one entry per step,
    mirroring a process's own step log) and `loop_steps_branches` (steps abandoned by an `on_error`
    recovery); both are read-only for callers.

    Args:
        name: The name of the step.
        steps: A static `StepList` used for every iteration, or a callable
            `(state, iteration) -> StepList` that builds one iteration's steps. If callable, it must
            be pure: `loop` calls it again on every resume instead of persisting the steps it built.
        until: Exit predicate over state, checked before each iteration. When it returns `True`,
            `loop` returns `Complete`.
        limit: Maximum number of iterations. Reaching it without `until` becoming `True` raises
            `LoopLimitReached`, which surfaces as `Failed`.
        on_error: Optional handler invoked when a step in the current iteration raises. Receives the
            error dict and the state as it was at the start of the failed iteration. May return a
            `StepList` to run as the rest of that iteration (recovery, not a new iteration), or
            `None` to propagate the original failure and end the loop. There is no other way to
            reach a further iteration after a failure, so a handler that wants one to happen must
            return steps that leave state in the shape `steps` expects for its next call.
    """

    def dispatching_form(state: State) -> FormGenerator:
        sub_step = _loop_resolve_sub_step(steps, on_error, name, state)
        form_generator = sub_step.form if sub_step is not None else None
        if form_generator is None:
            return {}
        return (yield from form_generator(state))

    def func(initial_state: State) -> Process:
        step_log_fn = step_log_fn_var.get()
        state: State = initial_state

        is_first_body = True
        iteration = _loop_derive_iteration(state, name)
        while True:
            if until(state):
                return Complete(state)

            if iteration >= limit:
                return Failed(LoopLimitReached(limit))

            iteration_start_state = state
            state, current_steps, position_base, resume_cursor = _loop_start_iteration(
                steps, name, state, initial_state, iteration
            )

            process, last_committed = _loop_run_steps(
                step_log_fn, name, state, current_steps, iteration, position_base, resume_cursor, not is_first_body
            )
            is_first_body = False

            process, last_committed = _loop_recover_from_failure(
                on_error, step_log_fn, name, iteration, iteration_start_state, process, last_committed
            )

            if process.issuspend():
                if until(process.unwrap()):
                    return Complete(process.unwrap())
                return process.map(lambda s: s | {"__replace_last_state": True})

            if not (process.issuccess() or process.isskipped()):
                return process

            iteration += 1
            state = {k: v for k, v in process.unwrap().items() if k not in (LOOP_SUB_STEP_KEY, LOOP_STEP_GROUP_KEY)}

    return make_step_function(func, name, dispatching_form, assignee=Assignee.NOC)


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
