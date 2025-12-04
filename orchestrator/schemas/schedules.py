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
from typing import Any, Dict, Literal
from uuid import UUID

from pydantic import BaseModel, Field, PrivateAttr

SCHEDULER_Q_CREATE = "create"
SCHEDULER_Q_UPDATE = "update"
SCHEDULER_Q_DELETE = "delete"


class APSchedulerJob(BaseModel):
    name: str | None = Field(None, description="Human readable name e.g. 'My Process'")


class APSchedulerJobCreate(APSchedulerJob):
    workflow_name: str = Field(..., description="Name of the workflow to run e.g. 'my_workflow_name'")
    workflow_id: UUID = Field(..., description="UUID of the workflow associated with this scheduled task")

    trigger: Literal["interval", "cron", "date"] = Field(..., description="APScheduler trigger type")
    trigger_kwargs: Dict[str, Any] = Field(
        default_factory=lambda: {},
        description="Arguments passed to the job function",
        examples=[{"hours": 12}, {"minutes": 30}, {"days": 1, "hours": 2}],
    )

    _scheduled_type: str = PrivateAttr(default=SCHEDULER_Q_CREATE)


class APSchedulerJobUpdate(APSchedulerJob):
    schedule_id: UUID = Field(..., description="UUID of the scheduled task")

    trigger: Literal["interval", "cron", "date"] | None = Field(None, description="APScheduler trigger type")
    trigger_kwargs: Dict[str, Any] | None = Field(
        default=None,
        description="Arguments passed to the job function",
        examples=[{"hours": 12}, {"minutes": 30}, {"days": 1, "hours": 2}],
    )

    _scheduled_type: str = PrivateAttr(default=SCHEDULER_Q_UPDATE)


class APSchedulerJobDelete(BaseModel):
    workflow_id: UUID = Field(..., description="UUID of the workflow associated with this scheduled task")
    schedule_id: UUID | None = Field(None, description="UUID of the scheduled task")

    _scheduled_type: str = PrivateAttr(default=SCHEDULER_Q_DELETE)
