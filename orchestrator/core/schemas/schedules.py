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
from typing import Annotated, Any, Literal, Self, Union
from uuid import UUID

from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pydantic import BaseModel, Field, TypeAdapter, model_validator

from orchestrator.core.workflow import default_user_inputs
from pydantic_forms.types import State

SCHEDULER_Q_CREATE = "create"
SCHEDULER_Q_UPDATE = "update"
SCHEDULER_Q_DELETE = "delete"

TRIGGER_TYPES: dict[str, type[BaseTrigger]] = {
    "interval": IntervalTrigger,
    "cron": CronTrigger,
    "date": DateTrigger,
}


def build_trigger(trigger: str, trigger_kwargs: dict[str, Any]) -> BaseTrigger:
    """Construct the APScheduler trigger for ``trigger``, raising ValueError/TypeError on bad kwargs."""
    if (trigger_cls := TRIGGER_TYPES.get(trigger)) is None:
        raise ValueError(f"Invalid trigger type: {trigger}")
    return trigger_cls(**trigger_kwargs)


def _validate_trigger_kwargs(trigger: str | None, trigger_kwargs: dict[str, Any] | None) -> None:
    """Fail schema validation if trigger_kwargs don't build a valid trigger.

    Returning a 422 at the API boundary beats silently dropping the job later in the scheduler queue.
    """
    if trigger is None:
        return
    try:
        build_trigger(trigger, trigger_kwargs or {})
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid trigger_kwargs for {trigger!r} trigger: {exc}") from exc


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
    user_inputs: list[State] = Field(default_factory=default_user_inputs, description="user inputs for the task")

    scheduled_type: Literal["create"] = Field("create", frozen=True)

    @model_validator(mode="after")
    def _check_trigger_kwargs(self) -> Self:
        _validate_trigger_kwargs(self.trigger, self.trigger_kwargs)
        return self


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

    @model_validator(mode="after")
    def _check_trigger_kwargs(self) -> Self:
        _validate_trigger_kwargs(self.trigger, self.trigger_kwargs)
        return self


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
