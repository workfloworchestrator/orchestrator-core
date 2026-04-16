"""Unit tests for :func:`orchestrator.workflow._run_step`.

These tests exercise the two-unit session lifecycle of ``_run_step``:

* Unit A (pre-step + execution) runs in its own ``database_scope`` / ``session.begin``
* Unit B (outcome logging) runs in a fresh ``database_scope`` / ``session.begin``
* Unit B always runs, even when Unit A raised.
"""

from __future__ import annotations

from typing import Any

from orchestrator.db import db
from orchestrator.workflow import Failed, Process, Step, Success, _run_step, make_step_function


def _make_step(name: str, body: Any) -> Step:
    """Wrap a plain callable into a Step with the minimum shape ``_run_step`` needs."""

    def runner(state: dict) -> Process:
        return body(state)

    return make_step_function(runner, name)


def test_run_step_happy_path_runs_body_and_logs_success() -> None:
    captured: dict[str, Any] = {}

    def body(state: dict) -> Process:
        return Success({**state, "ran": True})

    step = _make_step("happy", body)
    incoming: Process = Success({"reporter": "test"})

    def logstep(logged_step: Step, result: Process) -> Process:
        captured["step"] = logged_step
        captured["result"] = result
        return result

    returned = _run_step(step, incoming, logstep)

    assert captured["step"] is step
    assert captured["result"].issuccess()
    assert captured["result"].unwrap()["ran"] is True
    assert returned is captured["result"]


def test_run_step_body_raises_is_logged_as_failed() -> None:
    captured: dict[str, Any] = {}

    class Boom(RuntimeError):
        pass

    def body(state: dict) -> Process:
        raise Boom("kaboom")

    step = _make_step("explodes", body)
    incoming: Process = Success({"reporter": "test"})

    def logstep(logged_step: Step, result: Process) -> Process:
        captured["called"] = True
        captured["result"] = result
        return result

    returned = _run_step(step, incoming, logstep)

    assert captured.get("called") is True, "Unit B (logstep) must run even when Unit A raised"
    # Failed results are passed through on_failed(error_state_to_dict), so .isfailed() still holds.
    assert captured["result"].isfailed()
    assert returned is captured["result"]


def test_run_step_opens_distinct_scopes_for_units() -> None:
    tokens: dict[str, str] = {}

    def body(state: dict) -> Process:
        tokens["unit_a"] = db.request_context.get()
        return Success({**state, "unit_a_token": tokens["unit_a"]})

    step = _make_step("scoped", body)
    incoming: Process = Success({"reporter": "test"})

    def logstep(logged_step: Step, result: Process) -> Process:
        tokens["unit_b"] = db.request_context.get()
        return result

    _run_step(step, incoming, logstep)

    assert tokens["unit_a"], "Unit A must run inside a database_scope with a token"
    assert tokens["unit_b"], "Unit B must run inside a database_scope with a token"
    assert tokens["unit_a"] != tokens["unit_b"], "Unit A and Unit B must open distinct scopes"
