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

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import structlog
from pydantic import StringConstraints
from sqlalchemy import select
from typing_extensions import TypedDict

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.core.db import db
from orchestrator.core.db.models import WorkflowTable
from orchestrator.core.forms.validators import Choice
from orchestrator.core.forms.validators.timestamp import to_timestamp_field
from orchestrator.core.workflow import Workflow
from orchestrator.core.workflows import get_workflow
from pydantic_forms.types import FormGenerator, FormGeneratorAsync, State
from pydantic_forms.validators.components.read_only import read_only_field

logger = structlog.get_logger(__name__)


class ScheduleTypeEnum(Choice):
    DATE = "Once"
    INTERVAL = "Interval"
    CRON = "Cron"


class Intervals(Choice):
    ONE_HOUR = "1 hour"
    TWO_HOURS = "2 hours"
    FOUR_HOURS = "4 hours"
    TWELVE_HOURS = "12 hours"
    TWENTY_FOUR_HOURS = "24 hours"
    ONE_WEEK = "1 week"
    TWO_WEEKS = "2 weeks"
    ONE_MONTH = "1 months"


class ButtonConfig(TypedDict, total=False):
    text: str


class Buttons(TypedDict):
    previous: ButtonConfig
    next: ButtonConfig


INTERVAL_MAPPING = {
    Intervals.ONE_HOUR: {"hours": 1},
    Intervals.TWO_HOURS: {"hours": 2},
    Intervals.FOUR_HOURS: {"hours": 4},
    Intervals.TWELVE_HOURS: {"hours": 12},
    Intervals.TWENTY_FOUR_HOURS: {"hours": 24},
    Intervals.ONE_WEEK: {"weeks": 1},
    Intervals.TWO_WEEKS: {"weeks": 2},
    Intervals.ONE_MONTH: {"weeks": 4},
}

cron_regex = r"^(?:(\*|([0-5]?\d))(?:/(\d+))?\s+){4}(?:(\*|([0-5]?\d))(?:/(\d+))?\s+)?(?:([0-9,/*\-?LW#]+)(?:\s+([0-9,/*\-?LW#]+))?(?:\s+([0-9,/*\-?LW#]+))?)$"


def get_interval_kwargs(form_data: dict) -> dict:
    return {"start_date": form_data["start_date"]} | INTERVAL_MAPPING[form_data["interval"]]


def parse_cron_field(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def get_cron_kwargs(form_data: dict) -> dict:
    minute, hour, day, month, day_of_week = form_data["cron"].split(" ")

    return {
        "start_date": form_data["start_date"],
        "minute": parse_cron_field(minute),
        "hour": parse_cron_field(hour),
        "day": parse_cron_field(day),
        "month": parse_cron_field(month),
        "day_of_week": parse_cron_field(day_of_week),
    }


def _check_authorize(workflow: Workflow, user_model: OIDCUserModel | None) -> bool:
    result = workflow.authorize_callback(user_model)
    if asyncio.iscoroutine(result):
        result.close()
        return True
    return bool(result)


def get_tasks(user_model: OIDCUserModel | None) -> dict[str, tuple[Workflow, UUID, str]]:
    tasks = db.session.scalars(select(WorkflowTable))
    return {
        task_row.name: (workflow, task_row.workflow_id, task_row.description)
        for task_row in tasks
        if (workflow := get_workflow(task_row.name)) and _check_authorize(workflow, user_model)
    }


def has_initial_form(task: Workflow) -> bool:
    try:
        gen = task.initial_input_form({})
        form = next(gen)
        if form.model_fields:
            return True
    except StopIteration:
        return False
    except Exception as exc:
        logger.debug("Unexpected error when trying task.initial_input_form", task=task.name, error=exc)
        return True
    return False


def form_generator_send(form_generator: FormGenerator, data: dict | None) -> tuple[bool, dict]:
    try:
        return False, form_generator.send(data)  # type: ignore
    except StopIteration as e:
        return True, e.value


async def configure_schedule_form(state: State) -> FormGeneratorAsync:
    from orchestrator.core.forms import FormPage, SubmitFormPage

    user_model = OIDCUserModel(**_user_model) if (_user_model := state.get("user_model")) else None
    tasks = get_tasks(user_model)
    task_choices = {name: description for name, (_, _, description) in tasks.items()}

    class ScheduleTaskChoiceForm(FormPage):
        task: Choice("TaskChoices", task_choices)  # type: ignore

    schedule_task_form = yield ScheduleTaskChoiceForm

    task_name = schedule_task_form.task.name
    task, workflow_id, description = tasks[task_name]

    user_inputs = []
    if has_initial_form(task):
        form_state = {"workflow_target": task.target.value, "workflow_name": task.name} | state
        loop = asyncio.get_running_loop()
        sync_gen = task.initial_input_form(form_state)
        data = None
        while True:
            done, result = await loop.run_in_executor(None, form_generator_send, sync_gen, data)
            if done:
                break
            data = yield result
            user_inputs.append(data)

    class ScheduleTypeForm(FormPage):
        task: read_only_field(schedule_task_form.task)  # type: ignore
        schedule_type: ScheduleTypeEnum

    schedule_type_form = yield ScheduleTypeForm

    current_date = datetime.now(UTC)
    default_timestamp = int((current_date + timedelta(hours=1)).timestamp())
    DateTimeField = to_timestamp_field(min_date=current_date)

    class ScheduleDateForm(SubmitFormPage):
        task: read_only_field(schedule_type_form.task)  # type: ignore
        schedule_type: read_only_field(schedule_type_form.schedule_type)  # type: ignore

        start_date: DateTimeField = default_timestamp  # type: ignore
        if schedule_type_form.schedule_type == ScheduleTypeEnum.INTERVAL:
            interval: Intervals
        if schedule_type_form.schedule_type == ScheduleTypeEnum.CRON:
            cron: Annotated[str, StringConstraints(pattern=cron_regex)]

        buttons: Buttons = {"previous": {}, "next": {"text": "Create Schedule"}}

    schedule_date_form = yield ScheduleDateForm
    _schedule_type_data = schedule_date_form.model_dump()
    schedule_type_data = _schedule_type_data | {
        "start_date": datetime.fromtimestamp(_schedule_type_data["start_date"], UTC)
    }

    match schedule_date_form.schedule_type:
        case ScheduleTypeEnum.INTERVAL:
            trigger_kwargs = get_interval_kwargs(schedule_type_data)
        case ScheduleTypeEnum.CRON:
            trigger_kwargs = get_cron_kwargs(schedule_type_data)
        case _:
            trigger_kwargs = {"run_date": schedule_type_data["start_date"]}

    yield {
        "workflow_id": workflow_id,
        "workflow_name": task_name,
        "trigger": schedule_type_data["schedule_type"].name.lower(),
        "trigger_kwargs": trigger_kwargs,
        "user_inputs": user_inputs,
        "scheduled_type": "create",
        "name": description,
    }
