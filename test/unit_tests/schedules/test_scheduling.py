from unittest import mock

from typer.testing import CliRunner

from orchestrator.cli.scheduler import app

runner = CliRunner()


@mock.patch("orchestrator.cli.scheduler.get_paused_scheduler")
def test_run_scheduler(mock_get_paused_scheduler):
    mock_scheduler = mock.MagicMock()
    mock_scheduler.resume.side_effect = KeyboardInterrupt
    mock_get_paused_scheduler.return_value.__enter__.return_value = mock_scheduler

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 130


@mock.patch("orchestrator.cli.scheduler.get_paused_scheduler")
def test_show_schedule_command(mock_get_paused_scheduler):
    mock_job = mock.MagicMock()
    mock_job.id = "job1"
    mock_job.next_run_time = "2025-08-05 12:00:00"
    mock_job.trigger = "trigger_info"

    mock_scheduler = mock.MagicMock()
    mock_scheduler.get_jobs.return_value = [mock_job]
    mock_get_paused_scheduler.return_value.__enter__.return_value = mock_scheduler

    result = runner.invoke(app, ["show-schedule"])
    assert result.exit_code == 0
    assert "[job1]" in result.output
    assert "Next run: 2025-08-05 12:00:00" in result.output
    assert "trigger_info" in result.output


@mock.patch("orchestrator.cli.scheduler.get_paused_scheduler")
def test_force_command(mock_get_paused_scheduler):
    mock_job = mock.MagicMock()
    mock_job.id = "job1"
    mock_job.func = mock.MagicMock()

    mock_scheduler = mock.MagicMock()
    mock_scheduler.get_job.return_value = mock_job
    mock_get_paused_scheduler.return_value.__enter__.return_value = mock_scheduler

    result = runner.invoke(app, ["force", "job1"])
    assert result.exit_code == 0
    mock_job.func.assert_called_once()
    assert "Running job [job1] now..." in result.output
    assert "Job executed successfully" in result.output


@mock.patch("orchestrator.cli.scheduler.get_paused_scheduler")
def test_force_command_job_not_found(mock_get_paused_scheduler):
    mock_scheduler = mock.MagicMock()
    mock_scheduler.get_job.return_value = None
    mock_get_paused_scheduler.return_value.__enter__.return_value = mock_scheduler

    result = runner.invoke(app, ["force", "missing_job"])
    assert result.exit_code == 1
    assert "Job 'missing_job' not found" in result.output


@mock.patch("orchestrator.cli.scheduler.get_paused_scheduler")
def test_force_command_job_raises_exception(mock_get_paused_scheduler):
    def raise_exc(*args, **kwargs):
        raise RuntimeError("fail")

    mock_job = mock.MagicMock()
    mock_job.id = "job1"
    mock_job.func = raise_exc
    mock_job.args = ()
    mock_job.kwargs = {}

    mock_scheduler = mock.MagicMock()
    mock_scheduler.get_job.return_value = mock_job
    mock_get_paused_scheduler.return_value.__enter__.return_value = mock_scheduler

    result = runner.invoke(app, ["force", "job1"])
    assert result.exit_code == 1
    assert "Job execution failed: fail" in result.output
