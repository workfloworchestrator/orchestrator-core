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
from fastapi.routing import APIRouter
from sqlalchemy import text
from sqlalchemy.orm import contains_eager, defer, joinedload
from starlette.responses import Response

from orchestrator.api.error_handling import raise_status
from orchestrator.api.helpers import _query_with_filters
from orchestrator.db import (
    ProcessStepTable,
    ProcessSubscriptionTable,
    ProcessTable,
    SubscriptionCustomerDescriptionTable,
    SubscriptionTable,
    db,
)
from orchestrator.domain.base import SubscriptionModel
from orchestrator.schemas import SubscriptionDomainModelSchema, SubscriptionSchema, SubscriptionWorkflowListsSchema
from orchestrator.services.subscriptions import (
    RELATION_RESOURCE_TYPES,
    query_child_subscriptions_by_resource_types,
    query_parent_subscriptions_by_resource_types,
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
def subscriptions_all() -> List[SubscriptionSchema]:
    """Return subscriptions with only a join on products."""
    subscription_columns = [
        "subscription_id",
        "description",
        "status",
        "insync",
        "start_date",
        "end_date",
        "customer_id",
    ]
    query = """SELECT s.subscription_id, s.description as description, s.status, s.insync, s.start_date,
               s.end_date, s.customer_id,
               p.created_at as product_created_at, p.description as product_description,
               p.end_date as product_end_date, p.name as product_name,
               p.tag as product_tag, p.product_id as product_product_id, p.status as product_status,
               p.product_type as product_type
                FROM subscriptions s
                 JOIN products p ON s.product_id = p.product_id"""
    subscriptions = db.session.execute(text(query))
    result: List[SubscriptionSchema] = []
    for sub in subscriptions:
        sub_dict = dict(zip(subscription_columns, sub))
        product = {
            "description": sub["product_description"],
            "name": sub["product_name"],
            "product_id": sub["product_product_id"],
            "status": sub["product_status"],
            "product_type": sub["product_type"],
            "tag": sub["product_tag"],
        }
        sub_dict["product"] = product
        result.append(SubscriptionSchema.parse_obj(sub_dict))
    # validation the response doesn't work correct for nested responses: a unit test ensures schema correctness
    return result


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
    return query_parent_subscriptions_by_resource_types(RELATION_RESOURCE_TYPES, subscription_id).all()


@router.get("/child_subscriptions/{subscription_id}", response_model=List[SubscriptionSchema])
def child_subscriptions(subscription_id: UUID) -> List[SubscriptionTable]:
    return query_child_subscriptions_by_resource_types(RELATION_RESOURCE_TYPES, subscription_id).all()


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
