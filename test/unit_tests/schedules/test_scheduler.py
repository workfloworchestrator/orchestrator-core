# Copyright 2019-2026 SURF, GÉANT.
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

"""Tests for the scheduler job options (misfire_grace_time, coalesce) and the reporting of missed jobs."""

import threading
import time
from collections.abc import Iterator, MutableMapping
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_MISSED, JobExecutionEvent
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from structlog.testing import capture_logs

from orchestrator.core.schedules.scheduler import job_defaults, log_missed_job
from orchestrator.core.schedules.service import _add_scheduled_task, _update_scheduled_task
from orchestrator.core.schemas.schedules import APSchedulerJobCreate, APSchedulerJobUpdate

JOB_COUNT = 25
# Roughly the time start_process takes; with one thread, JOB_COUNT jobs take ~2.5s, far beyond the 1s default grace.
JOB_DURATION = 0.1


def create_payload(**options) -> APSchedulerJobCreate:
    return APSchedulerJobCreate(
        workflow_name="task_validate_products",
        workflow_id=uuid4(),
        trigger="interval",
        trigger_kwargs={"hours": 1},
        **options,
    )


@pytest.fixture
def known_workflow() -> Iterator[None]:
    with (
        mock.patch(
            "orchestrator.core.schedules.service.get_workflow_by_workflow_id",
            return_value=SimpleNamespace(description="Validate products"),
        ),
        mock.patch("orchestrator.core.schedules.service._add_linker_entry"),
    ):
        yield


@pytest.mark.parametrize(
    "options,expected",
    [
        pytest.param({}, {}, id="defaults-not-passed"),
        pytest.param({"misfire_grace_time": 60}, {"misfire_grace_time": 60}, id="misfire-grace-time"),
        pytest.param({"coalesce": False}, {"coalesce": False}, id="coalesce"),
        pytest.param(
            {"misfire_grace_time": 300, "coalesce": True}, {"misfire_grace_time": 300, "coalesce": True}, id="both"
        ),
    ],
)
def test_add_scheduled_task_passes_only_set_job_options(known_workflow, options, expected):
    scheduler_connection = mock.Mock()

    _add_scheduled_task(create_payload(**options), scheduler_connection)

    add_job_kwargs = scheduler_connection.add_job.call_args.kwargs
    assert {key: add_job_kwargs[key] for key in ("misfire_grace_time", "coalesce") if key in add_job_kwargs} == expected
    assert add_job_kwargs["hours"] == 1


@pytest.mark.parametrize(
    "options,expected",
    [
        pytest.param({}, {}, id="defaults-unchanged"),
        pytest.param({"misfire_grace_time": 60}, {"misfire_grace_time": 60}, id="misfire-grace-time"),
        pytest.param({"coalesce": False, "name": "renamed"}, {"coalesce": False, "name": "renamed"}, id="with-name"),
    ],
)
def test_update_scheduled_task_modifies_only_set_job_options(options, expected):
    job = mock.Mock()
    scheduler_connection = mock.Mock(get_job=mock.Mock(return_value=job))

    _update_scheduled_task(APSchedulerJobUpdate(schedule_id=uuid4(), **options), scheduler_connection)

    job.reschedule.assert_not_called()
    job.modify.assert_called_once_with(**expected)


def test_job_options_are_applied_to_the_apscheduler_job(known_workflow):
    scheduler_connection = BackgroundScheduler(job_defaults=job_defaults)

    _add_scheduled_task(create_payload(misfire_grace_time=120, coalesce=False), scheduler_connection)
    _add_scheduled_task(create_payload(), scheduler_connection)

    # APScheduler applies the job defaults to pending jobs when the scheduler starts
    scheduler_connection.start(paused=True)
    try:
        configured, default = scheduler_connection.get_jobs()
    finally:
        scheduler_connection.shutdown()
    assert (configured.misfire_grace_time, configured.coalesce) == (120, False)
    assert (default.misfire_grace_time, default.coalesce) == (1, True)


@pytest.mark.parametrize(
    "job,expected",
    [
        pytest.param(
            SimpleNamespace(name="Validate X", kwargs={"workflow_name": "task_validate_x"}, misfire_grace_time=1),
            {"name": "Validate X", "workflow_name": "task_validate_x", "misfire_grace_time": 1},
            id="existing-job",
        ),
        pytest.param(
            None, {"name": None, "workflow_name": None, "misfire_grace_time": None}, id="job-removed-after-firing"
        ),
    ],
)
def test_log_missed_job_logs_an_error_with_schedule_details(job, expected):
    run_time = datetime(2026, 10, 5, 11, tzinfo=timezone.utc)
    scheduler_connection = mock.Mock(get_job=mock.Mock(return_value=job))

    with capture_logs() as logs:
        log_missed_job(JobExecutionEvent(EVENT_JOB_MISSED, "schedule-1", "default", run_time), scheduler_connection)

    scheduler_connection.get_job.assert_called_once_with("schedule-1")
    assert logs == [
        {
            "event": "Scheduled task was skipped because it was not started within its misfire_grace_time",
            "log_level": "error",
            "schedule_id": "schedule-1",
            "scheduled_run_time": run_time,
        }
        | expected
    ]


def run_simultaneous_jobs(threads: int, **options) -> tuple[list[str], list[str], list[MutableMapping[str, Any]]]:
    """Schedule JOB_COUNT jobs on the same trigger time through _add_scheduled_task and wait until all are handled.

    Returns:
        The ids of the jobs that ran, the ids of the jobs that were missed, and the logs of log_missed_job.
    """
    scheduler_connection = BackgroundScheduler(
        executors={"default": ThreadPoolExecutor(threads)}, job_defaults=job_defaults
    )
    executed: list[str] = []
    missed: list[str] = []
    all_handled = threading.Event()

    def on_event(event: JobExecutionEvent) -> None:
        (executed if event.code == EVENT_JOB_EXECUTED else missed).append(event.job_id)
        if len(executed) + len(missed) == JOB_COUNT:
            all_handled.set()

    scheduler_connection.add_listener(on_event, EVENT_JOB_EXECUTED | EVENT_JOB_MISSED)
    scheduler_connection.add_listener(lambda event: log_missed_job(event, scheduler_connection), EVENT_JOB_MISSED)

    run_date = datetime.now(timezone.utc) + timedelta(seconds=1)
    with (
        mock.patch(
            "orchestrator.core.schedules.service.run_start_workflow_scheduler_task",
            side_effect=lambda **_: time.sleep(JOB_DURATION),
        ),
        capture_logs() as logs,
    ):
        for _ in range(JOB_COUNT):
            payload = create_payload(**options).model_copy(
                update={"trigger": "date", "trigger_kwargs": {"run_date": run_date}}
            )
            _add_scheduled_task(payload, scheduler_connection)

        scheduler_connection.start()
        try:
            assert all_handled.wait(timeout=1 + JOB_COUNT * JOB_DURATION + 10), "not all jobs were handled"
        finally:
            scheduler_connection.shutdown()

    return executed, missed, [log for log in logs if log["log_level"] == "error"]


@pytest.mark.parametrize(
    "threads,options",
    [
        pytest.param(1, {"misfire_grace_time": 60}, id="single-thread-with-misfire-grace-time"),
        pytest.param(JOB_COUNT, {}, id="thread-per-job-with-default-grace-time"),
    ],
)
def test_all_jobs_on_the_same_trigger_time_are_executed(known_workflow, threads, options):
    executed, missed, error_logs = run_simultaneous_jobs(threads, **options)

    assert len(executed) == JOB_COUNT
    assert missed == []
    assert error_logs == []


def test_jobs_missed_with_default_grace_time_are_reported(known_workflow):
    executed, missed, error_logs = run_simultaneous_jobs(1)

    assert missed, "with a single thread and the 1s default grace time some jobs should be missed"
    assert len(executed) + len(missed) == JOB_COUNT
    assert sorted(log["schedule_id"] for log in error_logs) == sorted(missed)
