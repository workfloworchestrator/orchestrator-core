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
from typing import Any
from uuid import UUID

import structlog
from fastapi import Depends
from fastapi.routing import APIRouter
from sqlalchemy import delete, select
from sqlalchemy.orm import contains_eager, defer, joinedload
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.api.error_handling import raise_status
from orchestrator.api.helpers import add_response_range, add_subscription_search_query_filter
from orchestrator.db import (
    ProcessStepTable,
    ProcessSubscriptionTable,
    ProcessTable,
    ProductTable,
    SubscriptionMetadataTable,
    SubscriptionTable,
    db,
)
from orchestrator.schemas import SubscriptionWorkflowListsSchema
from orchestrator.schemas.subscription import SubscriptionDomainModelSchema, SubscriptionWithMetadata
from orchestrator.security import authenticate
from orchestrator.services.subscriptions import (
    format_extended_domain_model,
    format_special_types,
    get_subscription,
    subscription_workflows,
)
from orchestrator.settings import app_settings
from orchestrator.types import SubscriptionLifecycle
from orchestrator.utils.deprecation_logger import deprecated_endpoint
from orchestrator.utils.get_subscription_dict import get_subscription_dict
from orchestrator.websocket import sync_invalidate_subscription_cache

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


@router.get(
    "/domain-model/{subscription_id}",
    response_model=SubscriptionDomainModelSchema | None,
)
async def subscription_details_by_id_with_domain_model(
    request: Request, subscription_id: UUID, response: Response, filter_owner_relations: bool = True
) -> dict[str, Any] | None:
    def _build_response(model: dict, etag: str) -> dict[str, Any] | None:
        if etag == request.headers.get("If-None-Match"):
            response.status_code = HTTPStatus.NOT_MODIFIED
            return None
        response.headers["ETag"] = etag
        filtered = format_extended_domain_model(model, filter_owner_relations=filter_owner_relations)
        return format_special_types(filtered)

    try:
        subscription, etag = await get_subscription_dict(subscription_id)
        return _build_response(subscription, etag)
    except ValueError as e:
        if str(e) == f"Subscription with id: {subscription_id}, does not exist":
            raise_status(HTTPStatus.NOT_FOUND, f"Subscription with id: {subscription_id}, not found")
        else:
            raise_status(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))


@router.get(
    "/search",
    response_model=list[SubscriptionWithMetadata],
)
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
    "/workflows/{subscription_id}",
    response_model=SubscriptionWorkflowListsSchema,
    response_model_exclude_none=True,
    deprecated=True,
    description="This endpoint is deprecated and will be removed in a future release. Please use the GraphQL query",
    dependencies=[Depends(deprecated_endpoint)],
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


@router.put("/{subscription_id}/set_in_sync", response_model=None, status_code=HTTPStatus.OK)
def subscription_set_in_sync(subscription_id: UUID, current_user: OIDCUserModel | None = Depends(authenticate)) -> None:
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
                sync_invalidate_subscription_cache(subscription.subscription_id)
            else:
                raise_status(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    f"Subscription {subscription_id} has still failed processes with id's: {failed_processes_list}",
                )
        else:
            logger.info("Subscription already in sync")
    except ValueError as e:
        raise_status(HTTPStatus.NOT_FOUND, str(e))
