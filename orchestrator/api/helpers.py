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

import functools
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from shlex import shlex
from typing import Any
from uuid import UUID

from deprecated import deprecated
from more_itertools import chunked, first
from sqlalchemy import Select, String, cast, func, select
from sqlalchemy.sql import expression
from starlette.responses import Response
from structlog import get_logger

from orchestrator.api.error_handling import raise_status
from orchestrator.db import ProcessTable, ProductTable, SubscriptionTable, db
from orchestrator.db.models import SubscriptionSearchView
from orchestrator.db.range.range import Selectable, apply_range_to_statement
from orchestrator.domain.base import SubscriptionModel
from orchestrator.utils.search_query import create_ts_query_string

logger = get_logger(__name__)


def _quote_if_kv_pair(token: str) -> str:
    return f'"{token}"' if ":" in token else token


def _process_text_query(q: str) -> str:
    quote = '"'
    if q.count(quote) % 2 == 1:
        q += quote  # Add missing closing quote
    lex = shlex(q)
    lex.whitespace_split = True
    lex.quotes = '"'
    try:
        return " ".join([_quote_if_kv_pair(token) for token in lex])
    except ValueError:
        logger.debug("Error parsing text query.")
        return q


def _add_sort_to_query(query: Select, sort: list[str] | None) -> Select:
    if sort is None or len(sort) < 2:
        return query

    for item in chunked(sort, 2):
        if item and len(item) == 2:
            order_by_expr = expression.desc if item[1].upper() == "DESC" else expression.asc
            if item[0] in ["product", "tag"]:
                field = "name" if item[0] == "product" else "tag"
                col = ProductTable.__dict__.get(field)
            else:
                col = SubscriptionTable.__dict__.get(item[0])

            if col:
                query = query.order_by(order_by_expr(col))
            else:
                raise_status(HTTPStatus.BAD_REQUEST, f"Unable to sort on unknown field: {item[0]}")
    return query


def query_with_filters(  # noqa: C901
    stmt: Select,
    sort: list[str] | None = None,
    filters: list[str] | None = None,
) -> Select:
    if filters is not None:
        for filter_ in chunked(filters, 2):
            if filter_ and len(filter_) == 2:
                field = filter_[0]
                value = filter_[1]
                value_as_bool = value.lower() in ("yes", "y", "ye", "true", "1", "insync")
                if value is not None:
                    if field.endswith("_gt"):
                        stmt = stmt.filter(SubscriptionTable.__dict__[field[:-3]] > value)
                    elif field.endswith("_gte"):
                        stmt = stmt.filter(SubscriptionTable.__dict__[field[:-4]] >= value)
                    elif field.endswith("_lte"):
                        stmt = stmt.filter(SubscriptionTable.__dict__[field[:-4]] <= value)
                    elif field.endswith("_lt"):
                        stmt = stmt.filter(SubscriptionTable.__dict__[field[:-3]] < value)
                    elif field.endswith("_ne"):
                        stmt = stmt.filter(SubscriptionTable.__dict__[field[:-3]] != value)
                    elif field == "insync":
                        stmt = stmt.filter(SubscriptionTable.insync.is_(value_as_bool))
                    elif field == "tags":
                        # For node and port selector form widgets
                        sub_values = value.split("-")
                        stmt = stmt.filter(func.lower(ProductTable.tag).in_([s.lower() for s in sub_values]))
                    elif field == "tag":
                        # For React table 7
                        sub_values = value.split("-")
                        stmt = stmt.filter(func.lower(ProductTable.tag).in_([s.lower() for s in sub_values]))
                    elif field == "product":
                        sub_values = value.split("-")
                        stmt = stmt.filter(func.lower(ProductTable.name).in_([s.lower() for s in sub_values]))
                    elif field == "status":
                        # For React table 7
                        statuses = value.split("-")
                        stmt = stmt.filter(SubscriptionTable.status.in_([s.lower() for s in statuses]))
                    elif field == "statuses":
                        # For port subscriptions
                        sub_values = value.split("-")
                        stmt = stmt.filter(SubscriptionTable.status.in_([s.lower() for s in sub_values]))
                    elif field == "organisation" or field == "customer" or field == "customer_id":
                        stmt = stmt.filter(SubscriptionTable.customer_id == value)
                    elif field == "tsv":
                        # Quote key:value tokens. This will use the FOLLOWED BY operator (https://www.postgresql.org/docs/13/textsearch-controls.html)
                        processed_text_query = _process_text_query(value)

                        logger.debug("Running full-text search query:", value=processed_text_query)
                        # TODO: Make 'websearch_to_tsquery' into a sqlalchemy extension
                        stmt = stmt.join(SubscriptionSearchView).filter(
                            func.websearch_to_tsquery("simple", processed_text_query).op("@@")(
                                SubscriptionSearchView.tsv
                            )
                        )

                    elif field in SubscriptionTable.__dict__:
                        stmt = stmt.filter(cast(SubscriptionTable.__dict__[field], String).ilike("%" + value + "%"))

    return _add_sort_to_query(stmt, sort)


def add_response_range(
    stmt: Selectable, range_: list[int] | None, response: Response, unit: str = "items"
) -> Selectable:
    if range_ is not None and len(range_) == 2:
        total = db.session.scalar(select(func.count()).select_from(stmt.subquery()))
        range_start, range_end = range_
        try:
            stmt = apply_range_to_statement(stmt, range_start, range_end)
        except ValueError as e:
            logger.exception(e)
            raise_status(HTTPStatus.BAD_REQUEST, str(e))

        response.headers["Content-Range"] = f"{unit} {range_start}-{range_end}/{total}"
    return stmt


MAX_QUERY_STRING_LENGTH = 512


def add_subscription_search_query_filter(stmt: Select, search_query: str) -> Select:
    """Filters the Select statement on the contents of the query string.

    The Select statement should read from SubscriptionTable as a source.
    The query will first be converted from camelCase to snake_case before parsing.
    """
    if len(search_query) > MAX_QUERY_STRING_LENGTH:
        raise_status(HTTPStatus.BAD_REQUEST, f"Max query length of {MAX_QUERY_STRING_LENGTH} characters exceeded.")

    ts_query = create_ts_query_string(search_query)
    return stmt.join(SubscriptionSearchView).filter(
        func.to_tsquery("simple", ts_query).op("@@")(SubscriptionSearchView.tsv)
    )


VALID_SORT_KEYS = {
    "creator": "created_by",
    "started": "started_at",
    "status": "last_status",
    "assignee": "assignee",
    "modified": "last_modified_at",
    "workflow": "workflow",
}


@dataclass
class ProductEnriched:
    product_id: UUID
    description: str
    name: str
    tag: str
    status: str
    product_type: str


@dataclass
class _Subscription:
    customer_id: UUID
    description: str
    end_date: float
    insync: bool
    start_date: float
    status: str
    subscription_id: UUID
    product: ProductEnriched


@dataclass
class _ProcessListItem:
    assignee: str
    created_by: str | None
    failed_reason: str | None
    last_modified_at: datetime
    pid: UUID
    started_at: datetime
    last_status: str
    last_step: str | None
    subscriptions: list[_Subscription]
    workflow: str
    workflow_target: str | None
    is_task: bool


@deprecated(
    "consolidated with `show_process` into enrich_process in `orchestrator.utils.enrich_process` from version 1.2.3, will be removed in 1.4"
)
def enrich_process(p: ProcessTable) -> _ProcessListItem:
    # p.subscriptions is a non JSON serializable AssociationProxy
    # So we need to build a list of Subscriptions here.
    subscriptions: list[_Subscription] = []
    for sub in p.subscriptions:
        prod = sub.product

        subscription = _Subscription(
            customer_id=sub.customer_id,
            description=sub.description,
            end_date=sub.end_date if sub.end_date else None,
            insync=sub.insync,
            start_date=sub.start_date if sub.start_date else None,
            status=sub.status,
            subscription_id=sub.subscription_id,
            product=ProductEnriched(
                product_id=prod.product_id,
                description=prod.description,
                name=prod.name,
                tag=prod.tag,
                status=prod.status,
                product_type=prod.product_type,
            ),
        )
        subscriptions.append(subscription)

    return _ProcessListItem(
        assignee=p.assignee,
        created_by=p.created_by,
        failed_reason=p.failed_reason,
        last_modified_at=p.last_modified_at,
        pid=p.process_id,
        started_at=p.started_at.timestamp(),
        last_status=p.last_status,
        last_step=p.last_step,
        subscriptions=subscriptions,
        workflow=str(p.workflow_name),
        workflow_target=first([ps.workflow_target for ps in p.process_subscriptions], None),
        is_task=p.is_task,
    )


def update_in(dct: dict | list, path: str, value: Any, sep: str = ".") -> None:
    """Update a value in a dict or list based on a path."""
    for x in path.split(sep):
        prev: dict | list
        if x.isdigit() and isinstance(dct, list):
            prev = dct
            dct = dct[int(x)]
        else:
            prev = dct
            dct = dict(dct).setdefault(x, {})
    prev[x] = value  # type: ignore


def get_in(dct: dict | list, path: str, sep: str = ".") -> Any:
    """Get a value in a dict or list using the path and get the resulting key's value."""
    prev: dict | list
    for x in path.split(sep):
        if x.isdigit() and isinstance(dct, list):
            prev, dct = dct, dct[int(x)]
        else:
            prev, dct = dct, dict(dct).get(x)  # type: ignore
    return prev[x]  # type: ignore


def getattr_in(obj: Any, attr: str) -> Any:
    """Get an instance attribute value by path."""

    def _getattr(obj: object, attr: str) -> Any:
        if isinstance(obj, list):
            return obj[int(attr)]

        if isinstance(obj, dict):
            return obj.get(attr)

        return getattr(obj, attr, None)

    return functools.reduce(_getattr, [obj] + attr.split("."))


def product_block_paths(subscription: SubscriptionModel | dict) -> list[str]:
    _subscription = subscription.model_dump() if isinstance(subscription, SubscriptionModel) else subscription

    def get_dict_items(d: dict) -> Generator:
        for k, v in d.items():
            if isinstance(v, dict):
                for k1, v1 in get_dict_items(v):
                    yield (f"{k}.{k1}", v1)
                yield (k, v)
            if isinstance(v, list):
                for index, list_item in enumerate(v):
                    if isinstance(list_item, dict):
                        for list_item_key, list_item_value in get_dict_items(list_item):
                            yield (f"{k}.{index}.{list_item_key}", list_item_value)
                        yield (f"{k}.{index}", list_item)

    return [path for path, value in get_dict_items(_subscription)]
