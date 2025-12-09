# Copyright 2019-2025 SURF.
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
from typing import Annotated, Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter

SCHEDULER_Q_CREATE = "create"
SCHEDULER_Q_UPDATE = "update"
SCHEDULER_Q_DELETE = "delete"


class APSchedulerJob(BaseModel):
    scheduled_type: Literal["create", "update", "delete"] = Field(..., description="Discriminator for job type")


class APSchedulerJobCreate(APSchedulerJob):
    name: str | None = Field(None, description="Human readable name e.g. 'My Process'")
    workflow_name: str = Field(..., description="Name of the workflow to run e.g. 'my_workflow_name'")
    workflow_id: UUID = Field(..., description="UUID of the workflow associated with this scheduled task")

    trigger: Literal["interval", "cron", "date"] = Field(..., description="APScheduler trigger type")
    trigger_kwargs: dict[str, Any] = Field(
        default_factory=lambda: {},
        description="Arguments passed to the trigger on job creation",
        examples=[{"hours": 12}, {"minutes": 30}, {"days": 1, "hours": 2}],
    )

    scheduled_type: Literal["create"] = Field("create", frozen=True)


class APSchedulerJobUpdate(APSchedulerJob):
    name: str | None = Field(None, description="Human readable name e.g. 'My Process'")
    schedule_id: UUID = Field(..., description="UUID of the scheduled task")

    trigger: Literal["interval", "cron", "date"] | None = Field(None, description="APScheduler trigger type")
    trigger_kwargs: dict[str, Any] | None = Field(
        default=None,
        description="Arguments passed to the job function",
        examples=[{"hours": 12}, {"minutes": 30}, {"days": 1, "hours": 2}],
    )

    scheduled_type: Literal["update"] = Field("update", frozen=True)


class APSchedulerJobDelete(APSchedulerJob):
    workflow_id: UUID = Field(..., description="UUID of the workflow associated with this scheduled task")
    schedule_id: UUID | None = Field(None, description="UUID of the scheduled task")

    scheduled_type: Literal["delete"] = Field("delete", frozen=True)


APSchedulerJobs = Annotated[
    Union[
        APSchedulerJobCreate,
        APSchedulerJobUpdate,
        APSchedulerJobDelete,
    ],
    Field(discriminator="scheduled_type"),
]
APSJobAdapter = TypeAdapter(APSchedulerJobs)  # type: ignore
