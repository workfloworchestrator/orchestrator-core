# Copyright 2019-2026 SURF, GÉANT, ESnet.
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
from apscheduler import version_info as apscheduler_version
from apscheduler.triggers.cron import CronTrigger
from pydantic import AfterValidator, ConfigDict
from sqlalchemy import select
from typing_extensions import TypedDict

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.core.db import db
from orchestrator.core.db.models import WorkflowTable
from orchestrator.core.forms.validators import Choice
from orchestrator.core.forms.validators.timestamp import to_timestamp_field
from orchestrator.core.utils.auth import AuthContext
from orchestrator.core.workflow import Workflow, default_user_inputs
from orchestrator.core.workflows import get_workflow
from pydantic_forms.types import FormGenerator, FormGeneratorAsync, State
from pydantic_forms.validators import callout
from pydantic_forms.validators.components.callout import CalloutMessageType
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


FasterIntervalCallout = callout(
    header="Need a finer interval?",
    message="The shortest option here is 1 hour. For anything shorter, down to seconds, "
    "switch to a Cron schedule instead.",
    message_type=CalloutMessageType.PRIMARY,
)


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


def get_interval_kwargs(form_data: dict) -> dict:
    return {"start_date": form_data["start_date"]} | INTERVAL_MAPPING[form_data["interval"]]


_APSCHEDULER_V3 = apscheduler_version < (4,)


def _day_of_week_shift(n: int) -> int:
    """Shift a crontab weekday number to APScheduler 3.x numbering.

    Crontab: 0=Sunday, 1=Monday..6=Saturday, 7=Sunday (alias).
    APScheduler 3.x: 0=Monday..6=Sunday. Formula: (n - 1) % 7.
    """
    if n not in range(0, 8):
        raise ValueError(f"{n!r} is not a valid weekday number (0–7)")
    return (n - 1) % 7


def _expand_and_shift(a: int, b: int, step: int) -> str:
    """Expand crontab range(a, b+1, step), shift each day, sort, and comma-join."""
    shifted_days = sorted(_day_of_week_shift(d) for d in range(a, b + 1, step))
    return ",".join(str(d) for d in shifted_days)


def _translate_dow_numeric_range(range_part: str, separator: str, step: str) -> str:
    """Translate a numeric A-B[/step] sub-expression to APScheduler 3.x."""
    a_str, _, b_str = range_part.partition("-")
    a, b = int(a_str), int(b_str)
    step_int = int(step) if separator else 1

    # Full-coverage range: spans all 7 weekdays (e.g. 0-6 or 0-7)
    if b - a + 1 >= 7:
        return "0-6" if not separator else _expand_and_shift(a, b, step_int)

    first, last = _day_of_week_shift(a), _day_of_week_shift(b)

    if first <= last:
        # Non-inverted: range order preserved after shifting
        return f"{first}-{last}/{step}" if separator else f"{first}-{last}"

    # Inverted (only when a == 0): expand if stepped, else split into "0-last,6"
    if separator:
        return _expand_and_shift(a, b, step_int)
    return "0,6" if last == 0 else f"0-{last},6"


def _translate_dow_expr(expr: str) -> str:
    """Translate one comma-separated sub-expression of a cron day_of_week field."""
    if any(c.isalpha() for c in expr):
        # named day or named range which APScheduler handles natively
        # also, _cron_field_error will raise APScheduler error in case of
        # "mixed" names & numerals (e.g., `mon-4`)
        return expr

    range_part, separator, step = expr.partition("/")

    if range_part == "*":
        return expr  # wildcard (with or without step) means no numeric shifting needed

    if "-" not in range_part:
        shifted = _day_of_week_shift(int(range_part))
        return f"{shifted}/{step}" if separator else str(shifted)

    return _translate_dow_numeric_range(range_part, separator, step)


def _translate_dow_for_apscheduler3(value: str) -> str:
    """Translate a cron day_of_week value from crontab convention to APScheduler 3.x.

    Crontab: 0=Sunday, 1=Monday..6=Saturday, 7=Sunday (alias).
    APScheduler 3.x: 0=Monday..6=Sunday.

    Named days (mon, tue, etc...) are left unchanged; APScheduler handles them natively.
    Numeric ranges whose shifted endpoints would be inverted are split or expanded
    so that APScheduler's ``RangeExpression`` never sees ``first > last``.
    """
    return ",".join(_translate_dow_expr(expr) for expr in value.split(","))


def _cron_fields(cron: str) -> dict[str, str]:
    """Map cron field strings to their CronTrigger keyword names.

    A 5-field expression is minute..day_of_week; a 6-field one adds a leading second.
    """
    fields = cron.split()
    match len(fields):
        case 5:
            names = ["minute", "hour", "day", "month", "day_of_week"]
        case 6:
            names = ["second", "minute", "hour", "day", "month", "day_of_week"]
        case _:
            raise ValueError(
                "A cron schedule needs 5 fields (minute hour day month day_of_week) or 6 with a leading second"
            )
    return dict(zip(names, fields, strict=True))


def _cron_field_error(name: str, value: str) -> str | None:
    """Return a field-scoped error message if ``value`` is invalid for cron field ``name``, else None.

    ``value`` is the raw user-typed value; for day_of_week it is translated before passing to
    CronTrigger so that crontab integers (0-7 Sunday alias) are accepted. See
    [Issue #1930](https://github.com/workfloworchestrator/orchestrator-core/issues/1930)
    Error messages always show the original user-typed value returned error values are unambiguous.
    """
    try:
        translated = _translate_dow_for_apscheduler3(value) if name == "day_of_week" and _APSCHEDULER_V3 else value
        CronTrigger(**{name: translated})
        return None
    except ValueError as exc:
        return f"{name} {value!r}: {exc}"


def validate_cron(cron: str) -> str:
    """Reject invalid cron expressions at form time.

    Each field is validated on its own (minute 0-59, hour 0-23, day 1-31, month 1-12, day_of_week
    0-7; a leading second 0-59 with 6 fields) so the error names the offending field(s) and reports
    all of them at once, instead of failing silently later in the scheduler queue.
    """
    if errors := [msg for name, value in _cron_fields(cron).items() if (msg := _cron_field_error(name, value))]:
        raise ValueError("; ".join(errors))
    return cron


def get_cron_kwargs(form_data: dict) -> dict:
    fields = _cron_fields(form_data["cron"])
    if _APSCHEDULER_V3:
        fields["day_of_week"] = _translate_dow_for_apscheduler3(fields["day_of_week"])
    return {"start_date": form_data["start_date"]} | fields


async def _check_authorize(workflow: Workflow, user_model: OIDCUserModel | None) -> bool:
    context = AuthContext(user=user_model, workflow=workflow, action="start_workflow")
    return await workflow.authorize_callback(context)


async def get_tasks(user_model: OIDCUserModel | None) -> dict[str, tuple[Workflow, UUID, str]]:
    tasks = db.session.scalars(select(WorkflowTable))
    return {
        task_row.name: (workflow, task_row.workflow_id, task_row.description)
        for task_row in tasks
        if (workflow := get_workflow(task_row.name)) and await _check_authorize(workflow, user_model)
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

    _model_config = ConfigDict(title="Create new schedule")
    user_model = OIDCUserModel(**_user_model) if (_user_model := state.get("user_model")) else None
    tasks = await get_tasks(user_model)
    task_choices = {name: description for name, (_, _, description) in tasks.items()}

    class ScheduleTaskChoiceForm(FormPage):
        model_config = _model_config
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
        model_config = _model_config
        task: read_only_field(schedule_task_form.task)  # type: ignore
        schedule_type: ScheduleTypeEnum

    schedule_type_form = yield ScheduleTypeForm

    current_date = datetime.now(UTC)
    default_timestamp = int((current_date + timedelta(hours=1)).timestamp())
    DateTimeField = to_timestamp_field(min_date=current_date)

    class ScheduleDateForm(SubmitFormPage):
        model_config = _model_config
        task: read_only_field(schedule_type_form.task)  # type: ignore
        schedule_type: read_only_field(schedule_type_form.schedule_type)  # type: ignore

        start_date: DateTimeField = default_timestamp  # type: ignore
        if schedule_type_form.schedule_type == ScheduleTypeEnum.INTERVAL:
            interval_callout: FasterIntervalCallout  # type: ignore[valid-type]
            interval: Intervals
        if schedule_type_form.schedule_type == ScheduleTypeEnum.CRON:
            cron: Annotated[str, AfterValidator(validate_cron)]

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
        "user_inputs": user_inputs or default_user_inputs(),
        "scheduled_type": "create",
        "name": description,
    }
