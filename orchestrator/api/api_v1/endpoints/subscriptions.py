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
from fastapi.routing import APIRouter
from oauth2_lib.fastapi import OIDCUserModel
from sqlalchemy.orm import contains_eager, defer, joinedload
from starlette.responses import Response

from orchestrator.api.error_handling import raise_status
from orchestrator.api.helpers import _query_with_filters
from orchestrator.db import (
    ProcessStepTable,
    ProcessSubscriptionTable,
    ProcessTable,
    SubscriptionCustomerDescriptionTable,
    SubscriptionInstanceTable,
    SubscriptionTable,
    db,
)
from orchestrator.domain.base import SubscriptionModel
from orchestrator.schemas import SubscriptionDomainModelSchema, SubscriptionSchema, SubscriptionWorkflowListsSchema
from orchestrator.security import oidc_user
from orchestrator.services.subscriptions import (
    get_subscription,
    query_child_subscriptions,
    query_parent_subscriptions,
    subscription_workflows,
)

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


@router.get("/all", response_model=List[SubscriptionSchema])
def subscriptions_all() -> List[SubscriptionTable]:
    """Return subscriptions with only a join on products."""
    return SubscriptionTable.query.all()


@router.get("/domain-model/{subscription_id}", response_model=SubscriptionDomainModelSchema)
def subscription_details_by_id_with_domain_model(subscription_id: UUID) -> Dict[str, Any]:
    customer_descriptions = SubscriptionCustomerDescriptionTable.query.filter(
        SubscriptionCustomerDescriptionTable.subscription_id == subscription_id
    ).all()

    subscription = SubscriptionModel.from_subscription(subscription_id).dict()
    subscription["customer_descriptions"] = customer_descriptions

    if not subscription:
        raise_status(HTTPStatus.NOT_FOUND)
    return subscription


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


@router.get("/parent_subscriptions/{subscription_id}", response_model=List[SubscriptionSchema])
def parent_subscriptions(subscription_id: UUID) -> List[SubscriptionTable]:
    return query_parent_subscriptions(subscription_id).all()


@router.get("/child_subscriptions/{subscription_id}", response_model=List[SubscriptionSchema])
def child_subscriptions(subscription_id: UUID) -> List[SubscriptionTable]:
    return query_child_subscriptions(subscription_id).all()


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
def subscription_instance_parents(subscription_instance_id: UUID) -> List[UUID]:
    subscription_instance = SubscriptionInstanceTable.query.get(subscription_instance_id)

    if not subscription_instance:
        raise_status(HTTPStatus.NOT_FOUND)

    return list(
        filter(
            lambda sub_id: sub_id != subscription_instance.subscription_id,
            {parent.subscription_id for parent in subscription_instance.parents},
        )
    )


@router.put("/{subscription_id}/set_in_sync", response_model=None, status_code=HTTPStatus.OK)
def subscription_set_in_sync(subscription_id: UUID, current_user: Optional[OIDCUserModel] = Depends(oidc_user)) -> None:
    def failed_processes() -> list:
        return (
            ProcessSubscriptionTable.query.join(ProcessTable)
            .filter(ProcessSubscriptionTable.subscription_id == subscription_id)
            .filter(~ProcessTable.is_task)
            .filter(ProcessTable.last_status != "completed")
            .all()
        )

    try:
        subscription = get_subscription(subscription_id, for_update=True)
        if not subscription.insync:
            logger.info(
                "Subscription not in sync, trying to change..", subscription_id=subscription_id, user=current_user
            )

            if not failed_processes():
                subscription.insync = True
                db.session.commit()
                logger.info("Subscription set in sync", user=current_user)
            else:
                raise_status(HTTPStatus.UNPROCESSABLE_ENTITY, f"Subscription {subscription_id} has still failed tasks")
        else:
            logger.info("Subscription already in sync")
    except ValueError as e:
        raise_status(HTTPStatus.NOT_FOUND, str(e))
