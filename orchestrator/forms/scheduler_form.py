import asyncio
import re
from datetime import datetime, timedelta
from typing import Annotated, Any

from annotated_types import Predicate
from sqlalchemy import select

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.db import db
from orchestrator.db.models import WorkflowTable
from orchestrator.forms.validators import Choice
from orchestrator.workflow import Workflow
from orchestrator.workflows import get_workflow
from pydantic_forms.core.shared import register_form
from pydantic_forms.types import FormGenerator, FormGeneratorAsync, State
from pydantic_forms.validators.components.read_only import read_only_field


class ScheduleTypeEnum(Choice):
    DATE = "Once"
    INTERVAL = "Interval"
    CRON = "Cron"


class Intervals(Choice):
    ONE_HOUR = "1 hour"
    TWO_HOURS = "2 hours"
    FOUR_HOURS = "4 hours"
    TWELVE_HOURS = "12 hours"
    TWENTY4_HOURS = "24 hours"
    ONE_WEEK = "1 week"
    TWO_WEEKS = "2 weeks"
    ONE_MONTH = "1 months"


INTERVAL_MAPPING = {
    Intervals.ONE_HOUR: {"hours": 1},
    Intervals.TWO_HOURS: {"hours": 2},
    Intervals.FOUR_HOURS: {"hours": 4},
    Intervals.TWELVE_HOURS: {"hours": 12},
    Intervals.TWENTY4_HOURS: {"hours": 24},
    Intervals.ONE_WEEK: {"weeks": 1},
    Intervals.TWO_WEEKS: {"weeks": 2},
    Intervals.ONE_MONTH: {"weeks": 4},
}

cron_regex = r"^(?:(\*|([0-5]?\d))(?:/(\d+))?\s+){4}(?:(\*|([0-5]?\d))(?:/(\d+))?\s+)?(?:([0-9,/*\-?LW#]+)(?:\s+([0-9,/*\-?LW#]+))?(?:\s+([0-9,/*\-?LW#]+))?)$"


def is_valid_cron(expression: str) -> bool:
    return bool(re.match(cron_regex, expression))


def get_tasks(user_model: OIDCUserModel | None) -> dict[str, WorkflowTable]:
    def is_allowed(task_row: WorkflowTable) -> bool:
        task = get_workflow(task_row.name)
        return bool(task and task.authorize_callback(user_model))

    tasks = db.session.scalars(select(WorkflowTable).filter(WorkflowTable.is_task))
    return {task.name: task for task in tasks if is_allowed(task)}


def has_initial_form(task: Workflow) -> bool:
    try:
        gen = task.initial_input_form({})
        form = next(gen)
        if form.model_fields:
            return True
    except StopIteration:
        return False
    except Exception:
        return True
    return False


def form_generator_send(form_generator: FormGenerator, data: dict | None) -> tuple[bool, dict]:
    try:
        return False, form_generator.send(data)  # type: ignore
    except StopIteration as e:
        return True, e.value


async def configure_schedule_form(state: State) -> FormGeneratorAsync:
    from orchestrator.forms import FormPage

    user_model = OIDCUserModel(**_user_model) if (_user_model := state.get("user_model")) else None
    tasks = get_tasks(user_model)
    task_choices = {name: workflow.description for name, workflow in tasks.items()}

    class ScheduleTypeForm(FormPage):
        task: Choice.__call__("TaskChoices", task_choices)  # type: ignore
        schedule_type: ScheduleTypeEnum

    schedule_type_form = yield ScheduleTypeForm
    schedule_type_data = schedule_type_form.model_dump()

    class ScheduleDateForm(FormPage):
        task: read_only_field(schedule_type_form.task)  # type: ignore
        schedule_type: read_only_field(schedule_type_form.schedule_type)  # type: ignore

        start_date: datetime = datetime.now() + timedelta(hours=1)
        if schedule_type_form.schedule_type == ScheduleTypeEnum.INTERVAL:
            interval: Intervals
        if schedule_type_form.schedule_type == ScheduleTypeEnum.CRON:
            cron: Annotated[str, Predicate(is_valid_cron)]

    schedule_date_form = yield ScheduleDateForm
    schedule_type_data = schedule_date_form.model_dump()

    task_name = schedule_type_form.task.name
    task_table_row = tasks[task_name]
    task = get_workflow(task_name)

    user_inputs = []
    if task and has_initial_form(task):
        form_state = {"workflow_target": task.target.value, "workflow_name": task.name} | state
        loop = asyncio.get_event_loop()
        sync_gen = task.initial_input_form(form_state)
        data = None
        while True:
            done, result = await loop.run_in_executor(None, form_generator_send, sync_gen, data)
            if done:
                form_state = result
                break
            data = yield result
            user_inputs.append(data)

    trigger_kwargs: dict[str, Any] = {}
    if schedule_date_form.schedule_type == ScheduleTypeEnum.INTERVAL:
        trigger_kwargs = INTERVAL_MAPPING[schedule_date_form.interval]
    if schedule_date_form.schedule_type == ScheduleTypeEnum.CRON:
        trigger_kwargs = {"cron": schedule_date_form.cron}

    yield schedule_type_data | {
        "workflow_id": task_table_row.workflow_id,
        "workflow_name": task_name,
        "trigger": schedule_type_data["schedule_type"],
        "trigger_kwargs": trigger_kwargs,
        "user_inputs": user_inputs,
    }


register_form("configure_schedule", configure_schedule_form)
