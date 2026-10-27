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

"""Helpers to run workflows and assert on their outcome in tests.

These functions run a workflow synchronously in the test thread, record every step in a step log and offer
assertions on the resulting :class:`~orchestrator.core.workflow.Process`. They need a configured database, see
:mod:`orchestrator.core.testing.fixtures`.
"""

import difflib
import pprint
from collections.abc import Callable
from dataclasses import replace
from itertools import chain, repeat
from types import TracebackType
from typing import Any, cast

import structlog

from orchestrator.core.db import WorkflowTable, db
from orchestrator.core.services.input_state import store_input_state
from orchestrator.core.services.processes import create_process, merge_state
from orchestrator.core.targets import Target
from orchestrator.core.utils.json import json_dumps, json_loads
from orchestrator.core.workflow import Process, ProcessStat, Step, Success, Workflow, runwf
from orchestrator.core.workflows import ALL_WORKFLOWS, LazyWorkflowInstance
from pydantic_forms.core import post_form
from pydantic_forms.types import FormGenerator, InputForm, State

logger = structlog.get_logger(__name__)

# The steps a workflow ran, each with the process state it produced
StepLog = list[tuple[Step, Process]]

DEFAULT_EXCLUDED_STATE_KEYS: tuple[str, ...] = ("process_id", "workflow_target", "workflow_name")

TEST_USER = "john.doe"


def store_workflow(wf: Workflow, name: str | None = None) -> WorkflowTable:
    """Insert a row in the workflows table for ``wf``, so processes can be started for it."""
    wf_table = WorkflowTable(
        name=name or wf.name,
        target=wf.target,
        is_task=wf.target in (Target.VALIDATE, Target.SYSTEM),
        description=wf.description,
    )
    db.session.add(wf_table)
    db.session.commit()
    return wf_table


def delete_workflow(wf: WorkflowTable) -> None:
    """Delete a row from the workflows table."""
    db.session.delete(wf)
    db.session.commit()


def _raise_exception(state: Any) -> Any:
    if isinstance(state, Exception):
        raise state
    return state


def assert_success(result: Process) -> None:
    """Assert that the process is Success. Re-raise the exception of a failed or waiting process."""
    assert result.on_failed(_raise_exception).on_waiting(_raise_exception).issuccess(), (
        f"Unexpected process status. Expected Success, but was: {result}"
    )


def assert_waiting(result: Process) -> None:
    """Assert that the process is Waiting. Re-raise the exception of a failed process."""
    assert result.on_failed(_raise_exception).iswaiting(), (
        f"Unexpected process status. Expected Waiting, but was: {result}"
    )


def assert_awaiting_callback(result: Process) -> None:
    """Assert that the process is AwaitingCallback. Re-raise the exception of a failed process."""
    assert result.on_failed(_raise_exception).isawaitingcallback(), (
        f"Unexpected process status. Expected AwaitingCallback, but was: {result}"
    )


def assert_suspended(result: Process) -> None:
    """Assert that the process is Suspend, waiting for user input. Re-raise the exception of a failed process."""
    assert result.on_failed(_raise_exception).issuspend(), (
        f"Unexpected process status. Expected Suspend, but was: {result}"
    )


def assert_aborted(result: Process) -> None:
    """Assert that the process is Abort. Re-raise the exception of a failed process."""
    assert result.on_failed(_raise_exception).isabort(), f"Unexpected process status. Expected Abort, but was: {result}"


def assert_failed(result: Process) -> None:
    """Assert that the process is Failed."""
    assert result.isfailed(), f"Unexpected process status. Expected Failed, but was: {result}"


def assert_complete(result: Process) -> None:
    """Assert that the process is Complete. Re-raise the exception of a failed process."""
    assert result.on_failed(_raise_exception).iscomplete(), (
        f"Unexpected process status. Expected Complete, but was: {result}"
    )


def assert_state(result: Process, expected: State) -> None:
    """Assert that the process state contains every key and value of ``expected``."""
    state = result.unwrap()
    actual = {key: state[key] for key in expected}
    assert expected == actual, f"Invalid state. Expected superset of: {expected}, but was: {actual}"


def assert_state_equal(result: Process, expected: State, excluded_keys: list[str] | None = None) -> None:
    """Assert that the process state equals ``expected``, ignoring ``excluded_keys`` on both sides.

    ``excluded_keys`` defaults to ``process_id``, ``workflow_target`` and ``workflow_name``.
    """
    excluded = set(DEFAULT_EXCLUDED_STATE_KEYS if excluded_keys is None else excluded_keys)
    state = {key: value for key, value in extract_state(result).items() if key not in excluded}
    expected_state = {key: value for key, value in expected.items() if key not in excluded}

    assert state == expected_state, "Unexpected state:\n" + "\n".join(
        difflib.ndiff(pprint.pformat(state).splitlines(), pprint.pformat(expected_state).splitlines())
    )


def assert_assignee(log: StepLog, expected: str) -> None:
    """Assert that the last step in the step log is assigned to ``expected``."""
    actual = log[-1][0].assignee
    assert expected == actual, f"Unexpected assignee. Expected {expected}, but was: {actual}"


def assert_step_name(log: StepLog, expected: str) -> None:
    """Assert that the last step in the step log is named ``expected``."""
    actual = log[-1][0]
    assert actual.name == expected, f"Unexpected name. Expected {expected}, but was: {actual}"


def extract_state(result: Process) -> State:
    """Return the state dict of a process."""
    return result.unwrap()


def extract_error(result: Process) -> str | None:
    """Return the error message of a failed process, or None when the state has no error."""
    assert isinstance(result, Process), f"Expected a Process, but got {result!r} of type {type(result)}"
    assert not isinstance(result.s, Process), "Result contained a Process in a Process, this should not happen"

    return extract_state(result).get("error")


class WorkflowInstanceForTests(LazyWorkflowInstance):
    """Register a workflow defined in a test for the duration of a ``with`` block.

    Unlike :class:`~orchestrator.core.workflows.LazyWorkflowInstance` it takes the workflow object itself instead of
    an import path. Entering the block adds the workflow to ``ALL_WORKFLOWS`` and to the workflows table, leaving it
    removes both again.

    Example::

        @workflow("Test workflow", target=Target.SYSTEM)
        def my_wf() -> StepList:
            return begin >> my_step >> done

        with WorkflowInstanceForTests(my_wf, "my_wf"):
            result, process, step_log = run_workflow("my_wf", {})
    """

    package: str
    function: str
    is_callable: bool

    def __init__(self, workflow: Workflow, name: str) -> None:
        super().__init__("orchestrator.core.testing", name)
        self.workflow = workflow
        self.name = name

    def __enter__(self) -> WorkflowTable:
        ALL_WORKFLOWS[self.name] = self
        self.workflow_instance = store_workflow(self.workflow, name=self.name)
        return self.workflow_instance

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        del ALL_WORKFLOWS[self.name]
        delete_workflow(self.workflow_instance)
        del self.workflow_instance

    def instantiate(self) -> Workflow:
        """Return the workflow, named after this instance."""
        self.workflow.name = self.name
        return self.workflow

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"WorkflowInstanceForTests('{self.workflow}','{self.name}')"


def _store_step(step_log: StepLog) -> Callable[[ProcessStat, Step, Process], Process]:
    def __store_step(pstat: ProcessStat, step: Step, process: Process) -> Process:  # noqa: ARG001
        try:
            process = process.map(lambda s: json_loads(json_dumps(s)))
        except Exception:
            logger.exception("Step state is not valid json", process=process)

        state = process.unwrap()
        state.pop("__step_name_override", None)
        state.pop("__step_importance_override", None)
        for k in state.get("__remove_keys", []) + ["__remove_keys"]:
            state.pop(k, None)
        if state.pop("__replace_last_state", None):
            step_log[-1] = (step, process)
        else:
            step_log.append((step, process))
        return process

    return __store_step


def _sanitize_input(input_data: State | list[State]) -> list[State]:
    # To be backwards compatible convert single dict to list
    as_list = input_data if isinstance(input_data, list) else [input_data]

    # We need a copy here and we want to mimic the actual code that returns a serialized version of the state
    return cast(list[State], json_loads(json_dumps(as_list)))


def run_workflow(workflow_key: str, input_data: State | list[State]) -> tuple[Process, ProcessStat, StepLog]:
    """Start a workflow and run it in the current thread until it completes, fails or suspends.

    Args:
        workflow_key: Name of the workflow, as registered in ``ALL_WORKFLOWS``.
        input_data: User input for the initial form, one dict per form page. A single dict is a single page.

    Returns:
        The resulting process, the process stat (needed by :func:`resume_workflow`) and the step log.
    """
    # ATTENTION!! This code needs to be as similar as possible to `orchestrator.core.services.processes.start_process`
    # The main differences are: we use a different step log function, and we don't run in
    # a separate thread. Note: run_predicate evaluation happens inside create_process.
    user_data = _sanitize_input(input_data)

    pstat = create_process(workflow_key, user_data, TEST_USER)

    step_log: StepLog = []
    result = runwf(pstat, _store_step(step_log))
    return result, pstat, step_log


def resume_workflow(
    process: ProcessStat, step_log: StepLog, input_data: State | list[State]
) -> tuple[Process, StepLog]:
    """Resume a suspended or waiting workflow with user input.

    Args:
        process: The process stat returned by :func:`run_workflow`.
        step_log: The step log returned by :func:`run_workflow`. It is extended in place.
        input_data: User input for the form of the step the workflow is suspended on.

    Returns:
        The resulting process and the step log.
    """
    # ATTENTION!! This code needs to be as similar as possible to `orchestrator.core.services.processes.resume_process`
    # The main differences are: we use a different step log function, and we don't run in a separate thread
    user_data = _sanitize_input(input_data)

    persistent = [
        entry
        for entry in step_log
        if not (entry[1].isfailed() or entry[1].issuspend() or entry[1].iswaiting() or entry[1].isawaitingcallback())
    ]
    remaining_steps = process.workflow.steps[len(persistent) :]

    if step_log and (step_log[-1][1].issuspend() or step_log[-1][1].isawaitingcallback()):
        _, current_state = step_log[-1]
    elif persistent:
        _, current_state = persistent[-1]
    else:
        current_state = Success({})

    user_input = post_form(remaining_steps[0].form, current_state.unwrap(), user_data)
    state = current_state.map(lambda state: merge_state(state, user_input))
    store_input_state(process.process_id, user_input, "user_input")

    updated_process = replace(process, log=remaining_steps, state=state)
    result = runwf(updated_process, _store_step(step_log))
    return result, step_log


def run_form_generator(
    form_generator: FormGenerator, extra_inputs: list[State] | None = None
) -> tuple[list[dict], State]:
    """Run a form generator to get the resulting forms and result.

    Warning! This does not run the actual pydantic validation on purpose. However you should
    make sure that anything in extra_inputs matched the values and types as if the pydantic validation has
    been ran.

    Args:
        form_generator: A form generator
        extra_inputs: Optional list of user input dicts for each page in the generator.
                      If no input is given for a page an empty dict is used.
                      The default value from the form is used as default value for a field.

    Returns:
        A list of generated forms and the result state for the whole generator.

    Example:
        Given the following form generator:

        >>> from pydantic_forms.core import FormPage
        >>> def form_generator(state):
        ...     class TestForm(FormPage):
        ...         field: str = "foo"
        ...     user_input = yield TestForm
        ...     return {**user_input.model_dump(), "bar": 42}

        You can run this without extra_inputs
        >>> forms, result = run_form_generator(form_generator({"state_field": 1}))
        >>> forms
        [{'additionalProperties': False, 'properties': {'field': {'default': 'foo', 'title': 'Field', 'type': 'string'}}, 'title': 'unknown', 'type': 'object'}]
        >>> result
        {'field': 'foo', 'bar': 42}


        Or with extra_inputs:
        >>> forms, result = run_form_generator(form_generator({'state_field': 1}), [{'field':'baz'}])
        >>> forms
        [{'additionalProperties': False, 'properties': {'field': {'default': 'foo', 'title': 'Field', 'type': 'string'}}, 'title': 'unknown', 'type': 'object'}]
        >>> result
        {'field': 'baz', 'bar': 42}

    """
    forms: list[dict] = []
    result: State = {"s": 3}

    try:
        form = cast(InputForm, next(form_generator))
        forms.append(form.model_json_schema())
        for extra_input in chain(extra_inputs or [], repeat(cast(State, {}))):
            user_input_data = {field_name: field.default for field_name, field in form.model_fields.items()}
            user_input_data.update(extra_input)
            user_input = form.model_construct(**user_input_data)
            form = form_generator.send(user_input)
            forms.append(form.model_json_schema())
    except StopIteration as stop:
        result = stop.value

    return forms, result


__all__ = [
    "DEFAULT_EXCLUDED_STATE_KEYS",
    "StepLog",
    "WorkflowInstanceForTests",
    "assert_aborted",
    "assert_assignee",
    "assert_awaiting_callback",
    "assert_complete",
    "assert_failed",
    "assert_state",
    "assert_state_equal",
    "assert_step_name",
    "assert_success",
    "assert_suspended",
    "assert_waiting",
    "delete_workflow",
    "extract_error",
    "extract_state",
    "resume_workflow",
    "run_form_generator",
    "run_workflow",
    "store_workflow",
]
