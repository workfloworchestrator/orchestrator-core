# Copyright 2019-2020 SURF.
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

"""Module that implements process related API endpoints."""

from http import HTTPStatus
from typing import Any

import structlog
from graphql import GraphQLError
from more_itertools import chunked, first, flatten
from sqlalchemy import String, cast, func
from sqlalchemy.orm import load_only
from sqlalchemy.sql import expression
from sqlmodel import select
from sqlmodel.sql.expression import SelectOfScalar

from orchestrator.api.error_handling import raise_status
from orchestrator.api.helpers import VALID_SORT_KEYS
from orchestrator.db import db
from orchestrator.db.sql_models import ProcessSQLModel, StepSQLModel
from orchestrator.forms import generate_form
from orchestrator.graphql.pagination import Connection, PageInfo
from orchestrator.graphql.schemas.process import ProcessType
from orchestrator.graphql.types import CustomInfo, Sort, SortOrder
from orchestrator.graphql.utils.get_selected_fields import get_selected_fields
from orchestrator.services.processes import SYSTEM_USER, _recoverwf, _restore_log
from orchestrator.utils.helpers import to_snake
from orchestrator.workflow import ProcessStat
from orchestrator.workflows import get_workflow
from orchestrator.workflows.removed_workflow import removed_workflow

logger = structlog.get_logger(__name__)
process_field_keys = ProcessSQLModel.__fields__


def _handle_process_error(message: str, info: CustomInfo, **kwargs) -> None:  # type: ignore
    message = "Invalid Sort parameters"
    logger.debug(message, **kwargs)
    info.context.errors.append(GraphQLError(message=message, path=info.path))


def filter_processes(
    info: CustomInfo, query: SelectOfScalar[ProcessSQLModel], filter_by: list[str] | None
) -> SelectOfScalar[ProcessSQLModel]:
    if filter_by is not None:
        if len(filter_by) == 0 or (len(filter_by) % 2) > 0:
            raise_status(HTTPStatus.BAD_REQUEST, "Invalid number of filter arguments")

        for filter_pair in chunked(filter_by, 2):
            field, value = filter_pair
            field = field.lower()
            # ignoring typign errors for ProcessSQLModel props because SqlModel props are actually columns
            if value is not None:
                if field == "pid":
                    query = query.filter(cast(ProcessSQLModel.pid, String).ilike("%" + value + "%"))
                elif field == "istask":
                    value_as_bool = value.lower() in ("yes", "y", "ye", "true", "1", "ja")
                    query = query.filter(ProcessSQLModel.is_task.is_(value_as_bool))  # type: ignore
                elif field == "assignee":
                    assignees = value.split("-")
                    query = query.filter(ProcessSQLModel.assignee.in_(assignees))  # type: ignore
                elif field == "status":
                    statuses = value.split("-")
                    query = query.filter(ProcessSQLModel.last_status.in_(statuses))  # type: ignore
                elif field == "workflow":
                    query = query.filter(ProcessSQLModel.workflow.ilike("%" + value + "%"))  # type: ignore
                elif field == "creator":
                    query = query.filter(ProcessSQLModel.created_by.ilike("%" + value + "%"))  # type: ignore
                # TODO: Add query filters for subscriptions when it gets created in graphql, check processes_filterable endpoint.
                else:
                    _handle_process_error(f"Invalid filter '{field}'", info)
    return query


def sort_processes(
    info: CustomInfo,
    query: SelectOfScalar[ProcessSQLModel],
    sort_by: list[Sort] | None = None,
) -> SelectOfScalar[ProcessSQLModel]:
    if sort_by is not None:
        for item in sort_by:
            if item.field in VALID_SORT_KEYS:
                sort_key = VALID_SORT_KEYS[item.field]
                if item.order == SortOrder.DESC:
                    query = query.order_by(expression.desc(ProcessSQLModel.__dict__[sort_key]))
                else:
                    query = query.order_by(expression.asc(ProcessSQLModel.__dict__[sort_key]))
            else:
                _handle_process_error("Invalid Sort parameters", info, sort_by=sort_by)
    return query


def set_processes_range(
    query: SelectOfScalar[ProcessSQLModel], after: int, first: int
) -> SelectOfScalar[ProcessSQLModel]:
    if after is not None and first:
        if after >= after + first:
            msg = "range start must be lower than end"
            logger.exception(msg)
            raise_status(HTTPStatus.BAD_REQUEST, msg)
        query = query.offset(after).limit(first + 1)
    return query


def load_process(process: ProcessSQLModel) -> ProcessStat:
    workflow = get_workflow(process.workflow)

    if not workflow:
        workflow = removed_workflow

    log = _restore_log(process.steps)  # type: ignore
    pstate, remaining = _recoverwf(workflow, log)

    return ProcessStat(pid=process.pid, workflow=workflow, state=pstate, log=remaining, current_user=SYSTEM_USER)  # type: ignore


def populate_process_details(process: ProcessSQLModel, process_stat: ProcessStat) -> dict[str, Any]:
    # TODO: Add subscriptions to the first() when the model exists.
    subscription = first([], None)
    if subscription:
        product_id = subscription.product_id
        customer_id = subscription.customer_id
    else:
        product_id = None
        customer_id = None

    steps = process.steps

    current_state = process_stat.state.unwrap() if process_stat.state else None

    form = None
    if process_stat.log:
        form = process_stat.log[0].form
        pstat_steps = list(map(lambda step: StepSQLModel(name=step.name, status="pending"), process_stat.log))
        steps += pstat_steps

    generated_form = generate_form(form, current_state, []) if form and current_state else None
    return {
        "product_id": product_id,
        "customer_id": customer_id,
        "steps": [step.dict() for step in steps],
        "current_state": current_state,
        "form": generated_form,
    }


extra_field_list = ["form", "steps", "currentState"]


def from_pydantic_with_extra(
    process: ProcessSQLModel, extra: dict[str, Any] | None = None, selected_fields: list[str] | None = None
) -> ProcessType:
    extra = extra if extra else {}
    selected_fields = selected_fields if selected_fields else []
    has_extra_fields = [field for field in extra_field_list if field in selected_fields]

    if has_extra_fields:
        process_stat = load_process(process)
        extra = populate_process_details(process, process_stat) | extra
    return ProcessType.from_pydantic(process, extra)  # type: ignore


async def resolve_processes(
    info: CustomInfo,
    filter_by: list[tuple[str, str]] | None = None,
    sort_by: list[Sort] | None = None,
    first: int = 10,
    after: int = 0,
) -> Connection[ProcessType]:
    _filter: list[str] | None = list(flatten(filter_by)) if filter_by else None
    logger.info("processes_filterable() called", range=[after, after + first], sort=sort_by, filter=_filter)

    selected_fields = [to_snake(field) for field in get_selected_fields(info)]
    model_fields = [field for field in selected_fields if field in process_field_keys]
    query = select(ProcessSQLModel).options(load_only(*model_fields))

    query = filter_processes(info, query, _filter)
    query = sort_processes(info, query, sort_by)

    total = db.session.exec(select([func.count()]).select_from(query)).first()
    query = set_processes_range(query, after, first)

    processes = db.session.exec(query).all()
    has_next_page = len(processes) > first

    # exclude last item as it was fetched to know if there is a next page
    processes = processes[:first]
    processes_length = len(processes)
    start_cursor = after if processes_length else None
    end_cursor = after + processes_length - 1

    return Connection(
        page=[from_pydantic_with_extra(p, selected_fields=selected_fields) for p in processes] if processes else [],
        page_info=PageInfo(
            has_previous_page=bool(after),
            has_next_page=has_next_page,
            start_cursor=start_cursor,
            end_cursor=end_cursor,
            total_items=total if total else None,
        ),
    )
