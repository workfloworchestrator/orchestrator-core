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

from datetime import datetime
from typing import Any
from uuid import UUID

from orchestrator.core.db.models import WorkflowApschedulerJob
from orchestrator.core.schemas.base import OrchestratorBaseModel
from orchestrator.core.targets import Target


class ScheduleIndexSchema(OrchestratorBaseModel):
    """A schedule for search indexing: the scheduled workflow or task, plus when it runs.

    A schedule has no table of its own. The workflow comes from the `workflows_apscheduler_jobs` linker row and
    the name, trigger and next run time from the APScheduler job that row points to.
    """

    schedule_id: UUID
    name: str | None = None
    trigger: str
    next_run_time: datetime | None = None
    workflow_id: UUID
    workflow_name: str
    workflow_description: str | None = None
    workflow_target: Target
    is_task: bool

    @classmethod
    def from_schedule(cls, schedule: WorkflowApschedulerJob, job: Any) -> "ScheduleIndexSchema":
        """Combine a linker row with its APScheduler job.

        Args:
            schedule: The linker row, with its workflow loaded.
            job: The APScheduler `Job` with id `schedule.schedule_id`.
        """
        workflow = schedule.workflow
        return cls(
            schedule_id=UUID(schedule.schedule_id),
            name=job.name,
            trigger=str(job.trigger),
            next_run_time=job.next_run_time,
            workflow_id=workflow.workflow_id,
            workflow_name=workflow.name,
            workflow_description=workflow.description,
            workflow_target=workflow.target,
            is_task=workflow.is_task,
        )


def load_schedule_index_schema(schedule: WorkflowApschedulerJob) -> ScheduleIndexSchema | None:
    """Return the indexable form of a linker row, or None when its APScheduler job no longer exists."""
    # Imported lazily: the scheduler module imports the process service, which imports search indexing.
    from orchestrator.core.schedules.scheduler import get_scheduler_task

    job = get_scheduler_task(schedule.schedule_id)
    return ScheduleIndexSchema.from_schedule(schedule, job) if job else None
