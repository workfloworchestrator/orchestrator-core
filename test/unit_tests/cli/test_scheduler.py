"""Tests for CLI scheduler commands: run, force, show-schedule, and load-initial-schedule."""

import re
from types import SimpleNamespace
from unittest import mock

from typer.testing import CliRunner

from orchestrator.core.cli.scheduler import app

runner = CliRunner()


def _make_task(task_id: str = "task-1", name: str = "My Task", args=None, kwargs=None):
    def _func(*a, **k):
        pass

    return SimpleNamespace(
        id=task_id,
        name=name,
        func=_func,
        args=args,
        kwargs=kwargs,
        next_run_time=SimpleNamespace(replace=lambda **_: "2026-01-01 00:00:00"),
        trigger="interval",
    )


# --- run ---


def test_run_keyboard_interrupt_exits_130():
    """KeyboardInterrupt during scheduler startup results in exit code 130."""
    cm = mock.MagicMock()
    cm.__enter__ = mock.MagicMock(side_effect=KeyboardInterrupt)
    cm.__exit__ = mock.MagicMock(return_value=False)
    with mock.patch("orchestrator.cli.scheduler.get_scheduler", return_value=cm):
        result = runner.invoke(app, ["run"])
    assert result.exit_code == 130


# --- force ---


def test_force_task_not_found_exits_with_error():
    with mock.patch("orchestrator.cli.scheduler.get_scheduler_task", return_value=None):
        result = runner.invoke(app, ["force", "nonexistent-task"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_force_task_executes_successfully():
    task = _make_task(args=[1], kwargs={"flag": True})
    with mock.patch("orchestrator.cli.scheduler.get_scheduler_task", return_value=task):
        result = runner.invoke(app, ["force", "task-1"])
    assert result.exit_code == 0
    assert "executed successfully" in result.output


def test_force_task_execution_fails_exits_with_error():
    task = _make_task()
    task.func = mock.Mock(side_effect=RuntimeError("boom"))
    with mock.patch("orchestrator.cli.scheduler.get_scheduler_task", return_value=task):
        result = runner.invoke(app, ["force", "task-1"])
    assert result.exit_code == 1
    assert "failed" in result.output


def test_force_task_no_args_kwargs_uses_defaults():
    """Covers the `task.args or ()` and `task.kwargs or {}` branches."""
    task = _make_task(args=None, kwargs=None)
    call_log = []
    task.func = lambda *a, **k: call_log.append((a, k))
    with mock.patch("orchestrator.cli.scheduler.get_scheduler_task", return_value=task):
        result = runner.invoke(app, ["force", "task-1"])
    assert result.exit_code == 0
    assert call_log == [((), {})]


# --- load_initial_schedule ---


def _mock_schedule_deps(workflow_map: dict):
    """workflow_map: workflow_name -> workflow object or None."""

    def _get_workflow(name):
        return workflow_map.get(name)

    return mock.patch("orchestrator.cli.scheduler.get_workflow_by_name", side_effect=_get_workflow)


def _make_workflow(name: str):
    import uuid

    return SimpleNamespace(workflow_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, name)))


def test_load_initial_schedule_all_workflows_found():
    wf_names = [
        "task_resume_workflows",
        "task_clean_up_tasks",
        "task_validate_subscriptions",
        "task_validate_products",
    ]
    workflow_map = {name: _make_workflow(name) for name in wf_names}
    with (
        _mock_schedule_deps(workflow_map),
        mock.patch("orchestrator.cli.scheduler.add_unique_scheduled_task_to_queue") as mock_add,
    ):
        result = runner.invoke(app, ["load-initial-schedule"])
    assert result.exit_code == 0
    assert mock_add.call_count == 4
    assert "Skipping" not in result.output


def test_load_initial_schedule_one_missing_skips():
    wf_names = [
        "task_resume_workflows",
        "task_clean_up_tasks",
        "task_validate_subscriptions",
    ]
    workflow_map = {name: _make_workflow(name) for name in wf_names}
    with (
        _mock_schedule_deps(workflow_map),
        mock.patch("orchestrator.cli.scheduler.add_unique_scheduled_task_to_queue") as mock_add,
    ):
        result = runner.invoke(app, ["load-initial-schedule"])
    assert result.exit_code == 0
    assert mock_add.call_count == 3
    assert "Skipping" in result.output


def test_load_initial_schedule_all_missing():
    with (
        _mock_schedule_deps({}),
        mock.patch("orchestrator.cli.scheduler.add_unique_scheduled_task_to_queue") as mock_add,
    ):
        result = runner.invoke(app, ["load-initial-schedule"])
    assert result.exit_code == 0
    assert mock_add.call_count == 0
    assert result.output.count("Skipping") == 4


# --- show_schedule ---


def test_show_schedule_empty():
    with (
        mock.patch("orchestrator.cli.scheduler.get_all_scheduler_tasks", return_value=[]),
        mock.patch("orchestrator.schedules.service.get_linker_entries_by_schedule_ids", return_value=[]),
    ):
        result = runner.invoke(app, ["show-schedule"])
    assert result.exit_code == 0


def _to_ascii(line: str) -> str:
    return line.encode("ascii", "ignore").decode("ascii").strip()


def test_show_schedule_with_tasks():
    """Tasks linked via the API show source 'API'; others show 'decorator'."""
    task_api = _make_task(task_id="api-task", name="API Task")
    task_dec = _make_task(task_id="dec-task", name="Decorator Task")

    linker_entry = SimpleNamespace(schedule_id="api-task")

    with (
        mock.patch("orchestrator.cli.scheduler.get_all_scheduler_tasks", return_value=[task_api, task_dec]),
        mock.patch("orchestrator.schedules.service.get_linker_entries_by_schedule_ids", return_value=[linker_entry]),
    ):
        result = runner.invoke(app, ["show-schedule"], env={"COLUMNS": "300", "LINES": "200"})
    assert result.exit_code == 0

    output = "\n".join(_to_ascii(line) for line in result.output.splitlines())
    assert re.search(r"api-task\s+API Task\s+API", output)
    assert re.search(r"dec-task\s+Decorator Task\s+decorator", output)
