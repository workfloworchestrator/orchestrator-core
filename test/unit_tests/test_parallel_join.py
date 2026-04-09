"""Unit tests for parallel status logic: _worst_status, callback/inputstep rejection."""

import pytest

from orchestrator.workflow import (
    AwaitingCallback,
    Failed,
    Success,
    Suspend,
    Waiting,
)
from orchestrator.workflow import (
    _worst_status as worst_status,
)


@pytest.mark.parametrize(
    "results, expected_check",
    [
        ([Failed({"error": "boom"})], "isfailed"),
        ([Waiting({"w": 1})], "iswaiting"),
        ([Suspend({"s": 1})], "issuspend"),
        ([AwaitingCallback({"ac": 1})], "isawaitingcallback"),
        ([Success({"a": 1}), Success({"b": 2})], None),
        ([Waiting({"w": 1}), Failed({"error": "x"})], "isfailed"),
        ([Suspend({"s": 1}), Failed({"error": "x"})], "isfailed"),
        ([AwaitingCallback({"ac": 1}), Failed({"error": "x"})], "isfailed"),
        ([Suspend({"s": 1}), Waiting({"w": 1})], "iswaiting"),
        ([AwaitingCallback({"ac": 1}), Waiting({"w": 1})], "iswaiting"),
        ([AwaitingCallback({"ac": 1}), Suspend({"s": 1})], "issuspend"),
        ([Success({"a": 1}), Waiting({"w": 1}), Failed({"error": "x"})], "isfailed"),
        ([Success({"a": 1}), Suspend({"s": 1}), AwaitingCallback({"ac": 1})], "issuspend"),
    ],
    ids=[
        "single-failed",
        "single-waiting",
        "single-suspend",
        "single-awaiting-callback",
        "all-success",
        "waiting-and-failed",
        "suspend-and-failed",
        "awaiting-callback-and-failed",
        "suspend-and-waiting",
        "awaiting-callback-and-waiting",
        "awaiting-callback-and-suspend",
        "three-branches-failed-wins",
        "three-branches-suspend-wins",
    ],
)
def test_worst_status_priority(results: list, expected_check: str | None) -> None:
    worst = worst_status(results)
    if expected_check is None:
        assert worst is None
    else:
        assert worst is not None
        assert getattr(worst, expected_check)()


def test_callback_step_in_parallel_raises() -> None:
    from orchestrator.workflow import begin, callback_step, parallel, step

    @step("CB Action")
    def _cb_action() -> dict:
        return {}

    @step("CB Validate")
    def _cb_validate() -> dict:
        return {}

    _test_callback = callback_step("Test callback", _cb_action, _cb_validate)

    @step("Branch A")
    def branch_a() -> dict:
        return {"a": 1}

    with pytest.raises(ValueError, match="callback"):
        parallel("Invalid parallel", begin >> branch_a, begin >> _test_callback)


def test_callback_step_via_pipe_raises() -> None:
    from orchestrator.workflow import begin, callback_step, step

    @step("CB Action")
    def _cb_action() -> dict:
        return {}

    @step("CB Validate")
    def _cb_validate() -> dict:
        return {}

    _test_callback = callback_step("Test callback", _cb_action, _cb_validate)

    @step("Branch A")
    def branch_a() -> dict:
        return {"a": 1}

    with pytest.raises(ValueError, match="callback"):
        begin >> ((begin >> branch_a) | (begin >> _test_callback))
