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

"""Module that implements subscription related API endpoints."""
from http import HTTPStatus
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import Depends
from fastapi.param_functions import Body
from fastapi.routing import APIRouter
from sqlalchemy import delete, select
from sqlalchemy.orm import contains_eager, defer, joinedload
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.api.error_handling import raise_status
from orchestrator.api.helpers import add_response_range, add_subscription_search_query_filter, query_with_filters
from orchestrator.db import (
    ProcessStepTable,
    ProcessSubscriptionTable,
    ProcessTable,
    ProductTable,
    SubscriptionInstanceTable,
    SubscriptionMetadataTable,
    SubscriptionTable,
    db,
)
from orchestrator.domain.base import SubscriptionModel
from orchestrator.schemas import SubscriptionDomainModelSchema, SubscriptionSchema, SubscriptionWorkflowListsSchema
from orchestrator.schemas.subscription import SubscriptionWithMetadata
from orchestrator.security import oidc_user
from orchestrator.services.subscriptions import (
    _generate_etag,
    build_extended_domain_model,
    format_extended_domain_model,
    format_special_types,
    get_subscription,
    get_subscription_metadata,
    query_depends_on_subscriptions,
    query_in_use_by_subscriptions,
    subscription_workflows,
)
from orchestrator.settings import app_settings
from orchestrator.types import SubscriptionLifecycle
from orchestrator.utils.redis import from_redis

router = APIRouter()

logger = structlog.get_logger(__name__)


def _delete_subscription_tree(subscription: SubscriptionTable) -> None:
    db.session.delete(subscription)
    db.session.commit()


def _delete_process_subscriptions(process_subscriptions: list[ProcessSubscriptionTable]) -> None:
    for process_subscription in process_subscriptions:
        process_id = str(process_subscription.process_id)
        subscription_id = str(process_subscription.subscription_id)
        db.session.execute(delete(ProcessSubscriptionTable).filter(ProcessSubscriptionTable.process_id == process_id))
        db.session.execute(delete(ProcessStepTable).filter(ProcessStepTable.process_id == process_id))
        db.session.execute(delete(ProcessTable).filter(ProcessTable.process_id == process_id))
        subscription = db.session.scalars(
            select(SubscriptionTable).filter(SubscriptionTable.subscription_id == subscription_id)
        ).first()
        if subscription:
            _delete_subscription_tree(subscription)


def _filter_statuses(filter_statuses: str | None = None) -> list[str]:
    """Check valid filter statuses.

    Args:
        filter_statuses: the filters.

    Returns:
        list of filters

    """
    if not filter_statuses:
        return []

    logger.debug("Filters to query subscription on.", filter_statuses=filter_statuses)
    statuses = filter_statuses.split(",")
    for status in statuses:
        if status not in SubscriptionLifecycle.values():
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail=f"Status {status}, is not a valid `SubscriptionLifecycle`",
            )
    return statuses


@router.get("/all", response_model=list[SubscriptionSchema])
def subscriptions_all() -> list[SubscriptionTable]:
    """Return subscriptions with only a join on products."""
    stmt = select(SubscriptionTable)
    return list(db.session.scalars(stmt))


@router.get("/domain-model/{subscription_id}", response_model=Optional[SubscriptionDomainModelSchema])
def subscription_details_by_id_with_domain_model(
    request: Request, subscription_id: UUID, response: Response, filter_owner_relations: bool = True
) -> dict[str, Any] | None:
    def _build_response(model: dict, etag: str) -> dict[str, Any] | None:
        if etag == request.headers.get("If-None-Match"):
            response.status_code = HTTPStatus.NOT_MODIFIED
            return None
        response.headers["ETag"] = etag
        filtered = format_extended_domain_model(model, filter_owner_relations=filter_owner_relations)
        return format_special_types(filtered)

    if cache_response := from_redis(subscription_id):
        return _build_response(*cache_response)

    try:
        subscription_model = SubscriptionModel.from_subscription(subscription_id)
        extended_model = build_extended_domain_model(subscription_model)
        etag = _generate_etag(extended_model)
        return _build_response(extended_model, etag)
    except ValueError as e:
        if str(e) == f"Subscription with id: {subscription_id}, does not exist":
            raise_status(HTTPStatus.NOT_FOUND, f"Subscription with id: {subscription_id}, not found")
        else:
            raise_status(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))


@router.delete("/{subscription_id}", response_model=None)
def delete_subscription(subscription_id: UUID) -> None:
    stmt = select(ProcessSubscriptionTable).filter_by(subscription_id=subscription_id)
    all_process_subscriptions = list(db.session.scalars(stmt))
    if len(all_process_subscriptions) > 0:
        _delete_process_subscriptions(all_process_subscriptions)
        return

    subscription = db.session.get(SubscriptionTable, subscription_id)
    if not subscription:
        raise_status(HTTPStatus.NOT_FOUND)

    _delete_subscription_tree(subscription)
    return


@router.get("/in_use_by/{subscription_id}", response_model=list[SubscriptionSchema])
def in_use_by_subscriptions(
    subscription_id: UUID, filter_statuses: list[str] = Depends(_filter_statuses)
) -> list[SubscriptionTable]:
    """Retrieve subscriptions that are in use by this subscription.

    Args:
        subscription_id: Subscription to query
        filter_statuses: List of filters

    Returns:
        list of subscriptions

    """
    return query_in_use_by_subscriptions(subscription_id, filter_statuses).all()


@router.post("/subscriptions_for_in_used_by_ids", response_model=dict[UUID, SubscriptionSchema])
def subscriptions_by_in_used_by_ids(data: list[UUID] = Body(...)) -> dict[UUID, SubscriptionSchema]:
    rows = db.session.execute(
        select(SubscriptionInstanceTable)
        .join(SubscriptionTable)
        .filter(SubscriptionInstanceTable.subscription_instance_id.in_(data))
    ).all()
    result = {row[0].subscription_instance_id: row[0].subscription for row in rows}
    if len(rows) != len(data):
        logger.warning(
            "Not all subscription_instance_id's could be resolved.",
            unresolved_ids=list(set(data) - set(result.keys())),
        )
    return result


@router.get("/depends_on/{subscription_id}", response_model=list[SubscriptionSchema])
def depends_on_subscriptions(
    subscription_id: UUID,
    filter_statuses: list[str] = Depends(_filter_statuses),
) -> list[SubscriptionTable]:
    """Retrieve dependant subscriptions.

    Args:
        subscription_id: The subscription id
        filter_statuses: the status of dependant subscriptions

    Returns:
        List of dependant subscriptions.

    """
    return query_depends_on_subscriptions(subscription_id, filter_statuses).all()


@router.get("/", response_model=list[SubscriptionWithMetadata])
def subscriptions_filterable(
    response: Response, range: str | None = None, sort: str | None = None, filter: str | None = None
) -> list[dict]:
    """Get subscriptions filtered.

    Args:
        response: Fastapi Response object
        range: Range
        sort: Sort
        filter: Filter

    Returns:
        List of subscriptions

    """
    range_ = list(map(int, range.split(","))) if range else None
    sort_ = sort.split(",") if sort else None
    filter_ = filter.split(",") if filter else None
    logger.info("subscriptions_filterable() called", range=range_, sort=sort_, filter=filter_)
    stmt = select(SubscriptionTable, SubscriptionMetadataTable.metadata_).join_from(
        SubscriptionTable, SubscriptionMetadataTable, isouter=True
    )

    stmt = stmt.join(SubscriptionTable.product).options(
        contains_eager(SubscriptionTable.product), defer(SubscriptionTable.product_id)
    )
    stmt = query_with_filters(stmt, sort_, filter_)
    stmt = add_response_range(stmt, range_, response, unit="subscriptions")

    sequence = db.session.execute(stmt).all()
    return [{**s.__dict__, "metadata": md} for s, md in sequence]


@router.get("/search", response_model=list[SubscriptionWithMetadata])
def subscriptions_search(
    response: Response, query: str, range: str | None = None, sort: str | None = None
) -> list[dict]:
    """Get subscriptions filtered based on a search query string.

    Args:
        response: Fastapi Response object
        query: The search query
        range: Range
        sort: Sort

    Returns:
        List of subscriptions

    """
    range_ = list(map(int, range.split(","))) if range else None
    sort_ = sort.split(",") if sort else None
    logger.info("subscriptions_search() called", range=range_, sort=sort_)
    stmt = select(SubscriptionTable, SubscriptionMetadataTable.metadata_).join_from(
        SubscriptionTable, SubscriptionMetadataTable, isouter=True
    )

    stmt = stmt.join(SubscriptionTable.product).options(
        contains_eager(SubscriptionTable.product), defer(SubscriptionTable.product_id)
    )
    stmt = add_subscription_search_query_filter(stmt, query)
    stmt = add_response_range(stmt, range_, response, unit="subscriptions")
    sequence = db.session.execute(stmt).all()
    return [{**s.__dict__, "metadata": md} for s, md in sequence]


@router.get(
    "/workflows/{subscription_id}", response_model=SubscriptionWorkflowListsSchema, response_model_exclude_none=True
)
def subscription_workflows_by_id(subscription_id: UUID) -> dict[str, list[dict[str, list[Any] | str]]]:
    subscription = db.session.get(
        SubscriptionTable,
        subscription_id,
        options=[
            joinedload(SubscriptionTable.product),
            joinedload(SubscriptionTable.product).joinedload(ProductTable.workflows),
        ],
    )
    if not subscription:
        raise_status(HTTPStatus.NOT_FOUND)

    return subscription_workflows(subscription)


@router.get("/instance/other_subscriptions/{subscription_instance_id}", response_model=list[UUID])
def subscription_instance_in_use_by(
    subscription_instance_id: UUID, filter_statuses: list[str] = Depends(_filter_statuses)
) -> list[UUID]:
    subscription_instance = db.session.get(SubscriptionInstanceTable, subscription_instance_id)

    if not subscription_instance:
        raise_status(HTTPStatus.NOT_FOUND)

    in_use_by_instances = subscription_instance.in_use_by
    if filter_statuses:
        in_use_by_instances = [sub for sub in in_use_by_instances if sub.subscription.status in filter_statuses]

    unique_ids = {sub.subscription_id for sub in in_use_by_instances}
    return [sub_id for sub_id in unique_ids if sub_id != subscription_instance.subscription_id]


@router.put("/{subscription_id}/set_in_sync", response_model=None, status_code=HTTPStatus.OK)
def subscription_set_in_sync(subscription_id: UUID, current_user: OIDCUserModel | None = Depends(oidc_user)) -> None:
    def failed_processes() -> list[str]:
        if app_settings.DISABLE_INSYNC_CHECK:
            return []
        stmt = (
            select(ProcessSubscriptionTable)
            .join(ProcessTable)
            .filter(ProcessSubscriptionTable.subscription_id == subscription_id)
            .filter(~ProcessTable.is_task)
            .filter(ProcessTable.last_status != "completed")
            .filter(ProcessTable.last_status != "aborted")
        )
        _failed_processes = db.session.scalars(stmt)
        return [str(p.process_id) for p in _failed_processes]

    try:
        subscription = get_subscription(subscription_id, for_update=True)
        if not subscription.insync:
            logger.info(
                "Subscription not in sync, trying to change..", subscription_id=subscription_id, user=current_user
            )
            failed_processes_list = failed_processes()
            if not failed_processes_list:
                subscription.insync = True
                db.session.commit()
                logger.info("Subscription set in sync", user=current_user)
            else:
                raise_status(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    f"Subscription {subscription_id} has still failed processes with id's: {failed_processes_list}",
                )
        else:
            logger.info("Subscription already in sync")
    except ValueError as e:
        raise_status(HTTPStatus.NOT_FOUND, str(e))


@router.get("/{subscription_id}/metadata", status_code=HTTPStatus.OK)
def subscription_metadata(subscription_id: UUID) -> dict | None:
    return get_subscription_metadata(str(subscription_id))
