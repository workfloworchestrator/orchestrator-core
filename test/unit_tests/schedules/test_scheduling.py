from unittest import mock

from typer.testing import CliRunner

from orchestrator.cli.scheduler import app

runner = CliRunner()


@mock.patch("orchestrator.schedules.scheduler.scheduler")
def test_run_scheduler(mock_scheduler):
    mock_scheduler.start.side_effect = KeyboardInterrupt

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 130


@mock.patch("orchestrator.schedules.scheduler.get_scheduler_store")
def test_show_schedule_command(mock_get_scheduler_store):
    mock_job = mock.MagicMock()
    mock_job.id = "job1"
    mock_job.next_run_time = "2025-08-05 12:00:00"
    mock_job.trigger = "trigger_info"

    mock_scheduler = mock.MagicMock()
    mock_scheduler.get_all_jobs.return_value = [mock_job]
    mock_get_scheduler_store.return_value.__enter__.return_value = mock_scheduler

    result = runner.invoke(app, ["show-schedule"])
    assert result.exit_code == 0
    assert "[job1]" in result.output
    assert "Next run: 2025-08-05 12:00:00" in result.output
    assert "trigger_info" in result.output


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
