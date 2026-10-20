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

"""Unit tests for the database-free helpers in ``orchestrator.core.testing``."""

from types import SimpleNamespace

import pytest

from orchestrator.core.testing import (
    assert_aborted,
    assert_assignee,
    assert_awaiting_callback,
    assert_complete,
    assert_failed,
    assert_state,
    assert_state_equal,
    assert_step_name,
    assert_success,
    assert_suspended,
    assert_waiting,
    extract_error,
    extract_state,
    run_form_generator,
)
from orchestrator.core.testing.workflows import _sanitize_input
from orchestrator.core.workflow import Abort, AwaitingCallback, Complete, Failed, Skipped, Success, Suspend, Waiting
from pydantic_forms.core import FormPage

STATE = {"a": 1}
ALL_PROCESSES = {
    "success": Success(STATE),
    "skipped": Skipped(STATE),
    "suspend": Suspend(STATE),
    "waiting": Waiting(STATE),
    "awaiting_callback": AwaitingCallback(STATE),
    "abort": Abort(STATE),
    "failed": Failed(STATE),
    "complete": Complete(STATE),
}
STATUS_ASSERTIONS = [
    (assert_success, "success"),
    (assert_suspended, "suspend"),
    (assert_waiting, "waiting"),
    (assert_awaiting_callback, "awaiting_callback"),
    (assert_aborted, "abort"),
    (assert_failed, "failed"),
    (assert_complete, "complete"),
]


@pytest.mark.parametrize(
    "assertion,status,process_name",
    [
        (assertion, status, name)
        for assertion, status in STATUS_ASSERTIONS
        for name in ALL_PROCESSES
        # Failed or waiting processes with an exception as state re-raise it instead; tested separately
    ],
)
def test_status_assertions(assertion, status, process_name):
    process = ALL_PROCESSES[process_name]
    if process_name == status:
        assertion(process)
    else:
        with pytest.raises(AssertionError, match="Unexpected process status"):
            assertion(process)


@pytest.mark.parametrize(
    "assertion",
    [assert_success, assert_suspended, assert_awaiting_callback, assert_aborted, assert_complete, assert_waiting],
)
def test_status_assertions_reraise_exception_of_failed_process(assertion):
    error = ValueError("step failed")

    with pytest.raises(ValueError, match="step failed"):
        assertion(Failed(error))


def test_assert_success_reraises_exception_of_waiting_process():
    with pytest.raises(ValueError, match="retry later"):
        assert_success(Waiting(ValueError("retry later")))


def test_assert_failed_does_not_reraise_exception():
    assert_failed(Failed(ValueError("step failed")))


@pytest.mark.parametrize(
    "expected",
    [{}, {"a": 1}, {"a": 1, "b": [2]}],
)
def test_assert_state(expected):
    assert_state(Complete({"a": 1, "b": [2], "c": None}), expected)


@pytest.mark.parametrize(
    "expected,exception,match",
    [
        ({"a": 2}, AssertionError, "Invalid state"),
        ({"missing": 1}, KeyError, "missing"),
    ],
)
def test_assert_state_fails(expected, exception, match):
    with pytest.raises(exception, match=match):
        assert_state(Complete({"a": 1}), expected)


@pytest.mark.parametrize(
    "state,expected,excluded_keys",
    [
        ({"a": 1, "process_id": "x", "workflow_name": "wf"}, {"a": 1}, None),
        ({"a": 1}, {"a": 1, "workflow_target": "CREATE"}, None),
        ({"a": 1, "b": 2}, {"a": 1}, ["b"]),
        ({"a": 1, "process_id": "x"}, {"a": 1, "process_id": "x"}, []),
    ],
)
def test_assert_state_equal(state, expected, excluded_keys):
    assert_state_equal(Complete(state), expected, excluded_keys=excluded_keys)


@pytest.mark.parametrize(
    "state,expected,excluded_keys",
    [
        ({"a": 1}, {"a": 2}, None),
        ({"a": 1, "process_id": "x"}, {"a": 1}, []),
        ({"a": 1, "b": 2}, {"a": 1}, None),
    ],
)
def test_assert_state_equal_fails(state, expected, excluded_keys):
    with pytest.raises(AssertionError, match="Unexpected state"):
        assert_state_equal(Complete(state), expected, excluded_keys=excluded_keys)


def test_assert_state_equal_does_not_mutate_inputs():
    state = {"a": 1, "process_id": "x"}
    expected = {"a": 1, "process_id": "y"}

    assert_state_equal(Complete(state), expected)

    assert state == {"a": 1, "process_id": "x"}
    assert expected == {"a": 1, "process_id": "y"}


STEP_LOG: list = [
    (SimpleNamespace(name="First", assignee="SYSTEM"), Success({})),
    (SimpleNamespace(name="Second", assignee="NOC"), Suspend({})),
]


def test_assert_assignee_and_step_name_use_last_step():
    assert_assignee(STEP_LOG, "NOC")
    assert_step_name(STEP_LOG, "Second")


@pytest.mark.parametrize(
    "assertion,expected,match",
    [
        (assert_assignee, "SYSTEM", "Unexpected assignee"),
        (assert_step_name, "First", "Unexpected name"),
    ],
)
def test_assert_assignee_and_step_name_fail(assertion, expected, match):
    with pytest.raises(AssertionError, match=match):
        assertion(STEP_LOG, expected)


@pytest.mark.parametrize("process_name", list(ALL_PROCESSES))
def test_extract_state(process_name):
    assert extract_state(ALL_PROCESSES[process_name]) == STATE


@pytest.mark.parametrize(
    "process,expected",
    [
        (Failed({"error": "boom"}), "boom"),
        (Complete({"a": 1}), None),
    ],
)
def test_extract_error(process, expected):
    assert extract_error(process) == expected


@pytest.mark.parametrize(
    "result,match",
    [
        ({"error": "boom"}, "Expected a Process"),
        (Failed(Failed({"error": "boom"})), "Process in a Process"),
    ],
)
def test_extract_error_rejects_invalid_input(result, match):
    with pytest.raises(AssertionError, match=match):
        extract_error(result)


@pytest.mark.parametrize(
    "input_data,expected",
    [
        ({"a": 1}, [{"a": 1}]),
        ([{"a": 1}, {}], [{"a": 1}, {}]),
        ([], []),
    ],
)
def test_sanitize_input(input_data, expected):
    assert _sanitize_input(input_data) == expected


def test_sanitize_input_returns_json_serialized_copy():
    from uuid import UUID

    uuid = UUID("2f47f65a-0911-e511-80d0-005056956c1a")
    input_data = {"id": uuid, "nested": {"b": 2}}

    result = _sanitize_input(input_data)

    assert result == [{"id": str(uuid), "nested": {"b": 2}}]
    result[0]["nested"]["b"] = 3
    assert input_data["nested"]["b"] == 2


def _two_page_form(state):
    class FirstPage(FormPage):
        name: str = "default"

    first = yield FirstPage

    class SecondPage(FormPage):
        count: int = 1

    second = yield SecondPage
    return {**state, **first.model_dump(), **second.model_dump()}


@pytest.mark.parametrize(
    "extra_inputs,expected",
    [
        (None, {"s": 0, "name": "default", "count": 1}),
        ([], {"s": 0, "name": "default", "count": 1}),
        ([{"name": "x"}], {"s": 0, "name": "x", "count": 1}),
        ([{"name": "x"}, {"count": 5}], {"s": 0, "name": "x", "count": 5}),
    ],
)
def test_run_form_generator_multi_page(extra_inputs, expected):
    forms, result = run_form_generator(_two_page_form({"s": 0}), extra_inputs)

    assert [form["title"] for form in forms] == ["unknown", "unknown"]
    assert [list(form["properties"]) for form in forms] == [["name"], ["count"]]
    assert result == expected


def test_run_form_generator_without_pages():
    def no_pages(state):
        return state
        yield  # pragma: no cover

    forms, result = run_form_generator(no_pages({"a": 1}))

    assert forms == []
    assert result == {"a": 1}
