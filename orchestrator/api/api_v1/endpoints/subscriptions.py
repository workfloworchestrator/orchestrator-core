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
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import structlog
from fastapi import Depends
from fastapi.param_functions import Body
from fastapi.routing import APIRouter
from oauth2_lib.fastapi import OIDCUserModel
from sqlalchemy import select
from sqlalchemy.orm import contains_eager, defer, joinedload
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from orchestrator.api.error_handling import raise_status
from orchestrator.api.helpers import _query_with_filters
from orchestrator.db import (
    ProcessStepTable,
    ProcessSubscriptionTable,
    ProcessTable,
    SubscriptionInstanceTable,
    SubscriptionTable,
    db,
)
from orchestrator.domain.base import SubscriptionModel
from orchestrator.schemas import SubscriptionDomainModelSchema, SubscriptionSchema, SubscriptionWorkflowListsSchema
from orchestrator.security import oidc_user
from orchestrator.services.subscriptions import (
    _generate_etag,
    build_extended_domain_model,
    format_extended_domain_model,
    get_subscription,
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


def _delete_process_subscriptions(process_subscriptions: List[ProcessSubscriptionTable]) -> None:
    for process_subscription in process_subscriptions:
        pid = str(process_subscription.pid)
        subscription_id = str(process_subscription.subscription_id)
        ProcessSubscriptionTable.query.filter(ProcessSubscriptionTable.pid == pid).delete()
        ProcessStepTable.query.filter(ProcessStepTable.pid == pid).delete()
        ProcessTable.query.filter(ProcessTable.pid == pid).delete()
        subscription = SubscriptionTable.query.filter(SubscriptionTable.subscription_id == subscription_id).first()
        _delete_subscription_tree(subscription)


def _filter_statuses(filter_statuses: Optional[str] = None) -> List[str]:
    """
    Check valid filter statuses.

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


@router.get("/all", response_model=List[SubscriptionSchema])
def subscriptions_all() -> List[SubscriptionTable]:
    """Return subscriptions with only a join on products."""
    return SubscriptionTable.query.all()


@router.get("/domain-model/{subscription_id}", response_model=Optional[SubscriptionDomainModelSchema])
def subscription_details_by_id_with_domain_model(
    request: Request, subscription_id: UUID, response: Response, filter_owner_relations: bool = True
) -> Optional[Dict[str, Any]]:
    def _build_response(model: dict, etag: str) -> Optional[Dict[str, Any]]:
        if etag == request.headers.get("If-None-Match"):
            response.status_code = HTTPStatus.NOT_MODIFIED
            return None
        response.headers["ETag"] = etag
        return format_extended_domain_model(model, filter_owner_relations=filter_owner_relations)

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
    all_process_subscriptions = ProcessSubscriptionTable.query.filter_by(subscription_id=subscription_id).all()
    if len(all_process_subscriptions) > 0:
        _delete_process_subscriptions(all_process_subscriptions)
        return None
    else:
        subscription = SubscriptionTable.query.filter(SubscriptionTable.subscription_id == subscription_id).first()
        if not subscription:
            raise_status(HTTPStatus.NOT_FOUND)

        _delete_subscription_tree(subscription)
        return None


@router.get("/in_use_by/{subscription_id}", response_model=List[SubscriptionSchema])
def in_use_by_subscriptions(
    subscription_id: UUID, filter_statuses: List[str] = Depends(_filter_statuses)
) -> List[SubscriptionTable]:
    """
    Retrieve subscriptions that are in use by this subscription.

    Args:
        subscription_id: Subscription to query
        filter_statuses: List of filters

    Returns:
        list of subscriptions

    """
    return query_in_use_by_subscriptions(subscription_id, filter_statuses).all()


@router.post("/subscriptions_for_in_used_by_ids", response_model=Dict[UUID, SubscriptionSchema])
def subscriptions_by_in_used_by_ids(data: List[UUID] = Body(...)) -> Dict[UUID, SubscriptionSchema]:
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


@router.get("/depends_on/{subscription_id}", response_model=List[SubscriptionSchema])
def depends_on_subscriptions(
    subscription_id: UUID,
    filter_statuses: List[str] = Depends(_filter_statuses),
) -> List[SubscriptionTable]:
    """
    Retrieve dependant subscriptions.

    Args:
        subscription_id: The subscription id
        filter_statuses: the status of dependant subscriptions

    Returns:
        List of dependant subscriptions.

    """
    return query_depends_on_subscriptions(subscription_id, filter_statuses).all()


@router.get("/", response_model=List[SubscriptionSchema])
def subscriptions_filterable(
    response: Response, range: Optional[str] = None, sort: Optional[str] = None, filter: Optional[str] = None
) -> List[SubscriptionTable]:
    """
    Get subscriptions filtered.

    Args:
        response: Fastapi Response object
        range: Range
        sort: Sort
        filter: Filter

    Returns:
        List of subscriptions

    """
    _range: Union[List[int], None] = list(map(int, range.split(","))) if range else None
    _sort: Union[List[str], None] = sort.split(",") if sort else None
    _filter: Union[List[str], None] = filter.split(",") if filter else None
    logger.info("subscriptions_filterable() called", range=_range, sort=_sort, filter=_filter)
    query = SubscriptionTable.query.join(SubscriptionTable.product).options(
        contains_eager(SubscriptionTable.product), defer("product_id")
    )
    query_result = _query_with_filters(response, query, _range, _sort, _filter)
    return query_result


@router.get(
    "/workflows/{subscription_id}", response_model=SubscriptionWorkflowListsSchema, response_model_exclude_none=True
)
def subscription_workflows_by_id(subscription_id: UUID) -> Dict[str, List[Dict[str, Union[List[Any], str]]]]:
    subscription = SubscriptionTable.query.options(joinedload("product"), joinedload("product.workflows")).get(
        subscription_id
    )
    if not subscription:
        raise_status(HTTPStatus.NOT_FOUND)

    return subscription_workflows(subscription)


@router.get("/instance/other_subscriptions/{subscription_instance_id}", response_model=List[UUID])
def subscription_instance_in_use_by(
    subscription_instance_id: UUID, filter_statuses: List[str] = Depends(_filter_statuses)
) -> List[UUID]:
    subscription_instance: SubscriptionInstanceTable = SubscriptionInstanceTable.query.get(subscription_instance_id)

    if not subscription_instance:
        raise_status(HTTPStatus.NOT_FOUND)

    in_use_by_instances = subscription_instance.in_use_by
    if filter_statuses:
        in_use_by_instances = [sub for sub in in_use_by_instances if sub.subscription.status in filter_statuses]

    return list(
        filter(
            lambda sub_id: sub_id != subscription_instance.subscription_id,
            {sub.subscription_id for sub in in_use_by_instances},
        )
    )


@router.put("/{subscription_id}/set_in_sync", response_model=None, status_code=HTTPStatus.OK)
def subscription_set_in_sync(subscription_id: UUID, current_user: Optional[OIDCUserModel] = Depends(oidc_user)) -> None:
    def failed_processes() -> List[str]:
        if app_settings.DISABLE_INSYNC_CHECK:
            return []
        _failed_processes = (
            ProcessSubscriptionTable.query.join(ProcessTable)
            .filter(ProcessSubscriptionTable.subscription_id == subscription_id)
            .filter(~ProcessTable.is_task)
            .filter(ProcessTable.last_status != "completed")
            .filter(ProcessTable.last_status != "aborted")
            .all()
        )
        return [str(p.pid) for p in _failed_processes]

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
                    f"Subscription {subscription_id} has still failed processes with id's: {failed_processes}",
                )
        else:
            logger.info("Subscription already in sync")
    except ValueError as e:
        raise_status(HTTPStatus.NOT_FOUND, str(e))
