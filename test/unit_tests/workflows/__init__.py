import difflib
import pprint
from copy import deepcopy
from functools import reduce
from itertools import chain, repeat
from typing import Callable, Dict, List, Optional, Tuple, Union, cast
from uuid import uuid4

import structlog

from orchestrator.db import ProcessTable
from orchestrator.forms import post_process
from orchestrator.services.processes import StateMerger, _db_create_process
from orchestrator.types import FormGenerator, InputForm, State
from orchestrator.utils.json import json_dumps, json_loads
from orchestrator.workflow import Process as WFProcess
from orchestrator.workflow import ProcessStat, Step, Success, Workflow, runwf
from orchestrator.workflows import ALL_WORKFLOWS, LazyWorkflowInstance, get_workflow
from test.unit_tests.config import IMS_CIRCUIT_ID, PORT_SUBSCRIPTION_ID

logger = structlog.get_logger(__name__)


def _raise_exception(state):
    if isinstance(state, Exception):
        raise state
    return state


def assert_success(result):
    assert (
        result.on_failed(_raise_exception).on_waiting(_raise_exception).issuccess()
    ), f"Unexpected process status. Expected Success, but was: {result}"


def assert_waiting(result):
    assert result.on_failed(
        _raise_exception
    ).iswaiting(), f"Unexpected process status. Expected Waiting, but was: {result}"


def assert_suspended(result):
    assert result.on_failed(
        _raise_exception
    ).issuspend(), f"Unexpected process status. Expected Suspend, but was: {result}"


def assert_aborted(result):
    assert result.on_failed(_raise_exception).isabort(), f"Unexpected process status. Expected Abort, but was: {result}"


def assert_failed(result):
    assert result.isfailed(), f"Unexpected process status. Expected Failed, but was: {result}"


def assert_complete(result):
    assert result.on_failed(
        _raise_exception
    ).iscomplete(), f"Unexpected process status. Expected Complete, but was: {result}"


def assert_state(result, expected):
    state = result.unwrap()
    actual = {}
    for key in expected.keys():
        actual[key] = state[key]
    assert expected == actual, f"Invalid state. Expected superset of: {expected}, but was: {actual}"


def assert_state_equal(result: ProcessTable, expected: Dict, excluded_keys: Optional[List[str]] = None) -> None:
    """Test state with certain keys excluded from both actual and expected state."""
    if excluded_keys is None:
        excluded_keys = ["process_id", "workflow_target", "workflow_name"]
    state = deepcopy(extract_state(result))
    expected_state = deepcopy(expected)
    for key in excluded_keys:
        if key in state:
            del state[key]
        if key in expected_state:
            del expected_state[key]

    assert state == expected_state, "Unexpected state:\n" + "\n".join(
        difflib.ndiff(pprint.pformat(state).splitlines(), pprint.pformat(expected_state).splitlines())
    )


def assert_assignee(log, expected):
    actual = log[-1][0].assignee
    assert expected == actual, f"Unexpected assignee. Expected {expected}, but was: {actual}"


def assert_step_name(log, expected):
    actual = log[-1][0]
    assert actual.name == expected, f"Unexpected name. Expected {expected}, but was: {actual}"


def extract_state(result):
    return result.unwrap()


def extract_error(result):
    from orchestrator.workflow import Process

    assert isinstance(result, Process), f"Expected a Process, but got {repr(result)} of type {type(result)}"
    assert not isinstance(result.s, Process), "Result contained a Process in a Process, this should not happen"

    return extract_state(result).get("error")


class WorkflowInstanceForTests(LazyWorkflowInstance):
    """Register Test workflows.

    Similar to `LazyWorkflowInstance` but does not require an import during instantiate
    Used for creating test workflows
    """

    package: str
    function: str
    is_callable: bool

    def __init__(self, workflow: Workflow, name: str) -> None:
        self.workflow = workflow
        self.name = name

    def __enter__(self):
        ALL_WORKFLOWS[self.name] = self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        del ALL_WORKFLOWS[self.name]

    def instantiate(self) -> Workflow:
        """Import and instantiate a workflow and return it.

        This can be as simple as merely importing a workflow function. However, if it concerns a workflow generating
        function, that function will be called with or without arguments as specified.

        Returns:
            A workflow function.

        """
        self.workflow.name = self.name
        return self.workflow

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"WorkflowInstanceForTests('{self.workflow}','{self.name}')"


def _store_step(step_log: List[Tuple[Step, WFProcess]]) -> Callable[[ProcessStat, Step, WFProcess], WFProcess]:
    def __store_step(pstat: ProcessStat, step: Step, state: WFProcess) -> WFProcess:
        try:
            state = state.map(lambda s: json_loads(json_dumps(s)))
        except Exception:
            logger.exception("Step state is not valid json", state=state)
        step_log.append((step, state))
        return state

    return __store_step


def _sanitize_input(input_data: Union[State, List[State]]) -> List[State]:
    # To be backwards compatible convert single dict to list
    if not isinstance(input_data, List):
        input_data = [input_data]

    # We need a copy here and we want to mimic the actual code that returns a serialized version of the state
    return cast(List[State], json_loads(json_dumps(input_data)))


def run_workflow(workflow_key: str, input_data: Union[State, List[State]]) -> Tuple[WFProcess, ProcessStat, List]:
    # ATTENTION!! This code needs to be as similar as possible to `server.services.processes.start_process`
    # The main differences are: we use a different step log function and we don't run in
    # a sepperate thread
    user_data = _sanitize_input(input_data)
    user = "john.doe"

    step_log: List[Tuple[Step, WFProcess]] = []

    pid = uuid4()
    workflow = get_workflow(workflow_key)
    assert workflow, "Workflow does not exist"
    initial_state = {
        "process_id": pid,
        "reporter": user,
        "workflow_name": workflow_key,
        "workflow_target": workflow.target,
    }

    user_input = post_process(workflow.initial_input_form, initial_state, user_data)

    pstat = ProcessStat(
        pid, workflow=workflow, state=Success({**user_input, **initial_state}), log=workflow.steps, current_user=user
    )

    _db_create_process(pstat)

    result = runwf(pstat, _store_step(step_log))

    return result, pstat, step_log


def resume_workflow(
    process: ProcessStat, step_log: List[Tuple[Step, WFProcess]], input_data: State
) -> Tuple[WFProcess, List]:
    # ATTENTION!! This code needs to be as similar as possible to `server.services.processes.resume_process`
    # The main differences are: we use a different step log function and we don't run in
    # a sepperate thread
    user_data = _sanitize_input(input_data)

    persistent = list(filter(lambda p: not (p[1].isfailed() or p[1].issuspend() or p[1].iswaiting()), step_log))
    nr_of_steps_done = len(persistent)
    remaining_steps = process.workflow.steps[nr_of_steps_done:]

    _, current_state = step_log[-1]

    user_input = post_process(remaining_steps[0].form, current_state.unwrap(), user_data)
    state = current_state.map(lambda state: StateMerger.merge(deepcopy(state), user_input))

    updated_process = process.update(log=remaining_steps, state=state)
    result = runwf(updated_process, _store_step(step_log))
    return result, step_log


def assert_product_blocks_equal(expected, actual):
    def key_value_sort(item):
        name = list(item.keys())[0]
        if name == "Virtual Circuit":
            items = list(filter(lambda k: list(k.keys())[0] == IMS_CIRCUIT_ID, item["Virtual Circuit"]))
            id_ = items[0][IMS_CIRCUIT_ID]
            return f"1_{id_}"
        if name == "Service Attach Point":
            port_subscription_id = list(
                filter(lambda k: list(k.keys())[0] == PORT_SUBSCRIPTION_ID, item["Service Attach Point"])
            )
            port_subscription_id = port_subscription_id[0][PORT_SUBSCRIPTION_ID]
            vlanrange = list(filter(lambda k: list(k.keys())[0] == "vlanrange", item["Service Attach Point"]))
            vlanrange = vlanrange[0]["vlanrange"]
            return f"2_{port_subscription_id}_{vlanrange}"
        return name

    expected.sort(key=key_value_sort)
    actual.sort(key=key_value_sort)

    def accumulate_list_of_tuples(acc: List, dikt: Dict) -> List[Tuple]:
        acc.extend(dikt.items())
        return acc

    expected_product_block_names = [list(p.keys())[0] for p in expected]
    actual_product_block_names = [list(p.keys())[0] for p in actual]
    assert (
        expected_product_block_names == actual_product_block_names
    ), f"Expected the following product blocks: {expected_product_block_names}, but got {actual_product_block_names}"

    for expected_pb, actual_pb in zip(expected, actual):
        for expected_instance_values, actual_instance_values in zip(expected_pb.values(), actual_pb.values()):
            expected_tuples = set(reduce(accumulate_list_of_tuples, expected_instance_values, []))
            actual_tuples = set(reduce(accumulate_list_of_tuples, actual_instance_values, []))
            missing_instance_values = expected_tuples - actual_tuples
            unexpected_instance_values = actual_tuples - expected_tuples
            assert (
                not missing_instance_values
            ), f"Missing instance value(s): {missing_instance_values}; Unexpected: {unexpected_instance_values}"
            assert not unexpected_instance_values, f"Unexpected instance values: {unexpected_instance_values}"


def run_form_generator(
    form_generator: FormGenerator, extra_inputs: Optional[List[State]] = None
) -> Tuple[List[dict], State]:
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

        >>> from orchestrator.forms import FormPage
        >>> def form_generator(state):
        ...     class TestForm(FormPage):
        ...         field: str = "foo"
        ...     user_input = yield TestForm
        ...     return {**user_input.dict(), "bar": 42}

        You can run this without extra_inputs
        >>> forms, result = run_form_generator(form_generator({"state_field": 1}))
        >>> forms
        [{'title': 'unknown', 'type': 'object', 'properties': {'field': {'title': 'Field', 'default': 'foo', 'type': 'string'}}, 'additionalProperties': False}]
        >>> result
        {'field': 'foo', 'bar': 42}


        Or with extra_inputs:
        >>> forms, result = run_form_generator(form_generator({'state_field': 1}), [{'field':'baz'}])
        >>> forms
        [{'title': 'unknown', 'type': 'object', 'properties': {'field': {'title': 'Field', 'default': 'foo', 'type': 'string'}}, 'additionalProperties': False}]
        >>> result
        {'field': 'baz', 'bar': 42}

    """
    forms: List[dict] = []
    result: State = {"s": 3}
    if extra_inputs is None:
        extra_inputs = []

    try:
        form = cast(InputForm, next(form_generator))
        forms.append(form.schema())
        for extra_input in chain(extra_inputs, repeat(cast(State, {}))):
            user_input_data = {field_name: field.default for field_name, field in form.__fields__.items()}
            user_input_data.update(extra_input)
            user_input = form.construct(**user_input_data)
            form = form_generator.send(user_input)
            forms.append(form.schema())
    except StopIteration as stop:
        result = stop.value

    return forms, result
