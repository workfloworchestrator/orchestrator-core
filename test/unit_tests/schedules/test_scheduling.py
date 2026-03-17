import re
from datetime import datetime
from unittest import mock

from typer.testing import CliRunner

from orchestrator.cli.scheduler import app
from orchestrator.db.models import WorkflowApschedulerJob

runner = CliRunner()


@mock.patch("orchestrator.schedules.scheduler.scheduler")
def test_run_scheduler(mock_scheduler):
    mock_scheduler.start.side_effect = KeyboardInterrupt

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 130


def make_mock_job(id_, name, next_run_time_str, trigger):
    mock_job = mock.MagicMock()
    mock_job.id = id_
    mock_job.name = name
    mock_job.next_run_time = datetime.fromisoformat(next_run_time_str)
    mock_job.trigger = trigger
    return mock_job


def to_ascii_line(line: str):
    # Remove unicode from a rich.table outputted line
    return line.encode("ascii", "ignore").decode("ascii").strip()


def to_regex(mock_job, *, source):
    # Create regex to match mock job in show-schedule output
    return re.compile(rf"{mock_job.id}\s+{mock_job.name}\s+{source}\s+.*", flags=re.MULTILINE)


@mock.patch("orchestrator.schedules.service.get_linker_entries_by_schedule_ids")
@mock.patch("orchestrator.schedules.scheduler.get_scheduler_store")
def test_show_schedule_command(mock_get_scheduler_store, mock_get_linker_entries):
    # given
    mock_job1 = make_mock_job("job1", "My Job 1", "2025-08-05T12:00:00", "trigger_info")
    mock_job2 = make_mock_job("6faf2c63-44de-48bc-853d-bb3f57225055", "My Job 2", "2025-08-05T14:00:00", "trigger_info")

    mock_scheduler = mock.MagicMock()
    mock_scheduler.get_all_jobs.return_value = [mock_job1, mock_job2]
    mock_get_scheduler_store.return_value.__enter__.return_value = mock_scheduler

    mock_linker_entry_job2 = mock.MagicMock(spec=WorkflowApschedulerJob)
    mock_linker_entry_job2.schedule_id = mock_job2.id
    mock_get_linker_entries.return_value = [mock_linker_entry_job2]  # only job 2 is defined in API

    regex1 = to_regex(mock_job1, source="decorator")
    regex2 = to_regex(mock_job2, source="API")

    # when
    result = runner.invoke(app, ["show-schedule"], env={"COLUMNS": "300", "LINES": "200"})
    output_stripped = "\n".join([to_ascii_line(line) for line in result.output.splitlines()])

    # then
    assert regex1.findall(output_stripped) != [], f"Regex {regex1} did not match output {output_stripped}"
    assert regex2.findall(output_stripped) != [], f"Regex {regex2} did not match output {output_stripped}"


@mock.patch("orchestrator.schedules.scheduler.get_scheduler_store")
def test_force_command(mock_get_scheduler_store):
    mock_job = mock.MagicMock()
    mock_job.id = "test_task"
    mock_job.func = mock.MagicMock()

    mock_scheduler = mock.MagicMock()
    mock_scheduler.lookup_job.return_value = mock_job
    mock_get_scheduler_store.return_value.__enter__.return_value = mock_scheduler

    result = runner.invoke(app, ["force", "test_task"])
    assert result.exit_code == 0
    mock_job.func.assert_called_once()
    assert "Running Task [test_task] now..." in result.output
    assert "Task executed successfully" in result.output


@mock.patch("orchestrator.schedules.scheduler.get_scheduler_store")
def test_force_command_job_not_found(mock_get_scheduler_store):
    mock_scheduler = mock.MagicMock()
    mock_scheduler.lookup_job.return_value = None
    mock_get_scheduler_store.return_value.__enter__.return_value = mock_scheduler

    result = runner.invoke(app, ["force", "missing_task"])
    assert result.exit_code == 1
    assert "Task 'missing_task' not found" in result.output


@mock.patch("orchestrator.schedules.scheduler.get_scheduler_store")
def test_force_command_job_raises_exception(mock_get_scheduler_store):
    def raise_exc(*args, **kwargs):
        raise RuntimeError("fail")

    mock_job = mock.MagicMock()
    mock_job.id = "job1"
    mock_job.func = raise_exc
    mock_job.args = ()
    mock_job.kwargs = {}

    mock_scheduler = mock.MagicMock()
    mock_scheduler.lookup_job.return_value = mock_job
    mock_get_scheduler_store.return_value.__enter__.return_value = mock_scheduler

    result = runner.invoke(app, ["force", "job1"])
    assert result.exit_code == 1
    assert "Task execution failed: fail" in result.output
