import pytest
import schedule

from orchestrator.cli.scheduler import run
from orchestrator.schedules import ALL_SCHEDULERS
from orchestrator.schedules.scheduling import scheduler


def test_scheduling_with_period(capsys, monkeypatch):
    ref = {"called": False}

    @scheduler(name="test", time_unit="second", period=1)
    def test_scheduler():
        ref["called"] = True
        print("I've run")  # noqa: T001, T201
        return schedule.CancelJob

    ALL_SCHEDULERS.clear()
    ALL_SCHEDULERS.append(test_scheduler)

    # Avoid having to mock next_run() and idle_seconds() deep in the scheduler as we are only interested in the job:
    with pytest.raises(TypeError):
        run()
        captured = capsys.readouterr()
        assert captured.out == "I've run\n"
        assert ref["called"]
