from unittest import mock

from apscheduler.jobstores.memory import MemoryJobStore
from typer.testing import CliRunner

from orchestrator.cli.scheduler import app

runner = CliRunner()


@mock.patch("orchestrator.cli.scheduler.BlockingScheduler")
@mock.patch("orchestrator.cli.scheduler.get_pauzed_scheduler")
def test_run_scheduler_initializes_jobs(mock_get_pauzed_scheduler, mock_scheduler):
    mock_scheduler.return_value.start.side_effect = KeyboardInterrupt

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 130
    mock_get_pauzed_scheduler.assert_called_once()
    mock_scheduler.return_value.start.assert_called_once()


@mock.patch("orchestrator.schedules.scheduler.scheduler_dispose_db_connections")
def test_show_schedule_default_schedules(monkeypatch):
    in_memory_jobstores = {"default": MemoryJobStore()}
    monkeypatch.setattr("orchestrator.schedules.scheduler.jobstores", in_memory_jobstores)

    result = runner.invoke(app, ["show-schedule"])
    assert result.exit_code == 0
    assert "resume-workflows" in result.output
    assert "clean-tasks" in result.output
    assert "subscriptions-validator" in result.output
    assert "clean-tasks" in result.output


@mock.patch("orchestrator.cli.scheduler.get_pauzed_scheduler")
def test_force_command(mock_get_pauzed_scheduler):
    mock_job = mock.MagicMock()
    mock_job.id = "job1"
    mock_job.func = mock.MagicMock()

    mock_scheduler = mock.MagicMock()
    mock_scheduler.get_job.return_value = mock_job
    mock_get_pauzed_scheduler.return_value.__enter__.return_value = mock_scheduler

    result = runner.invoke(app, ["force", "job1"])
    assert result.exit_code == 0
    mock_job.func.assert_called_once()
    assert "Running job [job1] now..." in result.output
    assert "Job executed successfully" in result.output


@mock.patch("orchestrator.cli.scheduler.get_pauzed_scheduler")
def test_force_command_job_not_found(mock_get_pauzed_scheduler):
    mock_scheduler = mock.MagicMock()
    mock_scheduler.get_job.return_value = None
    mock_get_pauzed_scheduler.return_value.__enter__.return_value = mock_scheduler

    result = runner.invoke(app, ["force", "missing_job"])
    assert result.exit_code == 1
    assert "Job 'missing_job' not found" in result.output


@mock.patch("orchestrator.cli.scheduler.get_pauzed_scheduler")
def test_force_command_job_raises_exception(mock_get_pauzed_scheduler):
    def raise_exc(*args, **kwargs):
        raise RuntimeError("fail")

    mock_job = mock.MagicMock()
    mock_job.id = "job1"
    mock_job.func = raise_exc
    mock_job.args = ()
    mock_job.kwargs = {}

    mock_scheduler = mock.MagicMock()
    mock_scheduler.get_job.return_value = mock_job
    mock_get_pauzed_scheduler.return_value.__enter__.return_value = mock_scheduler

    result = runner.invoke(app, ["force", "job1"])
    assert result.exit_code == 1
    assert "Job execution failed: fail" in result.output
