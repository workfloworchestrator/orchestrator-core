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
from sqlalchemy import Text, and_, cast, or_, text
from sqlalchemy.orm import aliased, contains_eager, defer, joinedload, undefer
from sqlalchemy.orm.exc import MultipleResultsFound
from starlette.responses import Response

from orchestrator.api.error_handling import raise_status
from orchestrator.api.helpers import _query_with_filters
from orchestrator.db import (
    ProcessStepTable,
    ProcessSubscriptionTable,
    ProcessTable,
    ProductTable,
    ResourceTypeTable,
    SubscriptionCustomerDescriptionTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    SubscriptionTable,
    db,
)
from orchestrator.domain.base import SubscriptionModel
from orchestrator.schemas import (
    SubscriptionDetailsSchema,
    SubscriptionDomainModelSchema,
    SubscriptionIdSchema,
    SubscriptionSchema,
    SubscriptionWithPortAttrSchema,
    SubscriptionWorkflowListsSchema,
)
from orchestrator.services.subscriptions import (
    RELATION_RESOURCE_TYPES,
    get_subscription_details_by_id,
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


@router.get("/product_type/{product_type}", response_model=List[SubscriptionWithPortAttrSchema])
def subscriptions_by_product_type(product_type: str) -> List[SubscriptionWithPortAttrSchema]:
    subs = (
        SubscriptionTable.query.join(ProductTable)
        .options(undefer(SubscriptionTable.name), undefer(SubscriptionTable.tag), undefer(SubscriptionTable.port_mode))
        .filter(ProductTable.product_type == product_type)
        .all()
    )
    return subs


@router.get("/product_type/{product_type}/customer/{customer_id}", response_model=List[SubscriptionSchema])
def by_product_type_and_customer(product_type: str, customer_id: UUID) -> List[SubscriptionSchema]:
    """
    Retrieve Subscription by product type and customer id.

    This EndpointSchema is for the new Networkdashboard.

    :param product_type: Product Type out of the database.
    :param customer_id: Customer that is being queried.
    :return: List of Subscriptions
    """

    if product_type in ["LightPath", "IP", "L2VPN", "Firewall"]:
        # First retrieve all LightPaths, IP and L2VPN subscriptions

        product_type_filter = (
            or_(ProductTable.product_type == "IP", ProductTable.product_type == "Firewall")
            if product_type == "IP"
            else ProductTable.product_type == product_type
        )
        logger.debug("ProductTable type filter", product_type_filter=product_type_filter)
        subs = (
            SubscriptionTable.query.join(ProductTable)
            .options(
                undefer(SubscriptionTable.name),
                undefer(SubscriptionTable.tag),
                undefer(SubscriptionTable.port_mode),
                joinedload(SubscriptionTable.product),
                joinedload(SubscriptionTable.customer_descriptions),
            )
            .filter(SubscriptionTable.customer_id == customer_id)
            .filter(product_type_filter)
            .all()
        )

        port_subs = (
            db.session.query(cast(SubscriptionTable.subscription_id, Text))
            .join(ProductTable)
            .filter(SubscriptionTable.customer_id == customer_id, ProductTable.product_type == "Port")
            .subquery()
        )

        service_subs = (
            SubscriptionTable.query.join(ProductTable, SubscriptionInstanceTable, SubscriptionInstanceValueTable)
            .options(
                undefer(SubscriptionTable.name),
                undefer(SubscriptionTable.tag),
                undefer(SubscriptionTable.port_mode),
                joinedload(SubscriptionTable.product),
                joinedload(SubscriptionTable.customer_descriptions),
            )
            .filter(product_type_filter, SubscriptionInstanceValueTable.value.in_(port_subs))
            .all()
        )
        subs += service_subs

        return list(set(subs))
    else:
        subs = (
            SubscriptionTable.query.join(ProductTable)
            .options(
                undefer(SubscriptionTable.name),
                undefer(SubscriptionTable.tag),
                undefer(SubscriptionTable.port_mode),
                joinedload(SubscriptionTable.product),
                joinedload(SubscriptionTable.customer_descriptions),
            )
            .filter(SubscriptionTable.customer_id == customer_id)
            .filter(ProductTable.product_type == product_type)
            .all()
        )

        return list(set(subs))


@router.get("/customer/{customer_id}", response_model=List[SubscriptionWithPortAttrSchema])
def subscriptions_by_customer(customer_id: UUID) -> List[SubscriptionWithPortAttrSchema]:
    subs = (
        SubscriptionTable.query.options(
            undefer(SubscriptionTable.name),
            undefer(SubscriptionTable.tag),
            undefer(SubscriptionTable.port_mode),
            joinedload(SubscriptionTable.product),
        )
        .filter(SubscriptionTable.customer_id == customer_id)
        .all()
    )
    other_services_terminated_at_customer_ports: List[SubscriptionTable] = []
    for sub in subs:
        if sub.product.product_type == "Port":
            port_subs = (
                SubscriptionTable.query.join(SubscriptionInstanceTable)
                .join(SubscriptionInstanceValueTable)
                .join(ResourceTypeTable)
                .options(
                    undefer(SubscriptionTable.name),
                    undefer(SubscriptionTable.tag),
                    undefer(SubscriptionTable.port_mode),
                    joinedload(SubscriptionTable.product),
                )
                .filter(ResourceTypeTable.resource_type == "port_subscription_id")
                .filter(SubscriptionInstanceValueTable.value == str(sub.subscription_id))
                .filter(SubscriptionTable.customer_id != customer_id)
                .all()
            )
            if port_subs:
                other_services_terminated_at_customer_ports.extend(port_subs)

    subs.extend(other_services_terminated_at_customer_ports)

    return subs


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


@router.get("/ports", response_model=List[SubscriptionWithPortAttrSchema])
def port_subscriptions_filterable(
    response: Response, range: Optional[str] = None, sort: Optional[str] = None, filter: Optional[str] = None
) -> List[SubscriptionTable]:
    _range: Union[List[int], None] = list(map(int, range.split(","))) if range else None
    _sort: Union[List[str], None] = sort.split(",") if sort else None
    _filter: Union[List[str], None] = filter.split(",") if filter else None
    logger.info("port_subscriptions_filterable() called", range=_range, sort=_sort, filter=_filter)
    query = (
        SubscriptionTable.query.join(SubscriptionTable.product)
        .options(contains_eager(SubscriptionTable.product), defer("product_id"), undefer("port_mode"))
        .filter(ProductTable.product_type == "Port")
    )
    query_result = _query_with_filters(response, query, _range, _sort, _filter)

    return query_result


@router.get("/nsi", response_model=SubscriptionIdSchema)
def nsi_light_path_subscription(
    port_subscription_id_1: UUID, vlan_1: int, port_subscription_id_2: UUID, vlan_2: int
) -> Dict[str, UUID]:
    """
    Retrieve an NSI LightPath SubscriptionTable ID for OpenNSA.

    This is a custom endpoint in the orchestrator to support the OpenNSA deployment. It is necessary to be compatible
    with OpenNSA. The OpenNSA only has a notion of interfaces and vlans, not of deployed LightPaths. It searches for
    deployed LightPaths with the port and vlan combination.

    Args:
        port_subscription_id_1: PortSchema one
        vlan_1: vlan 1
        port_subscription_id_2: PortSchema 2
        vlan_2: vlan 2

    Returns:
        {"subscription_id": UUID}

    """
    Port1InstanceValue = aliased(SubscriptionInstanceValueTable)
    Vlan1InstanceValue = aliased(SubscriptionInstanceValueTable)
    Port2InstanceValue = aliased(SubscriptionInstanceValueTable)
    Vlan2InstanceValue = aliased(SubscriptionInstanceValueTable)
    SAP1 = aliased(SubscriptionInstanceTable)
    SAP2 = aliased(SubscriptionInstanceTable)

    try:
        subscription = (
            SubscriptionTable.query.join(SAP1, SAP1.subscription_id == SubscriptionTable.subscription_id)
            .join(SAP2, SAP2.subscription_id == SubscriptionTable.subscription_id)
            .join(Port1InstanceValue, Port1InstanceValue.subscription_instance_id == SAP1.subscription_instance_id)
            .join(Vlan1InstanceValue, Vlan1InstanceValue.subscription_instance_id == SAP1.subscription_instance_id)
            .join(Port2InstanceValue, Port2InstanceValue.subscription_instance_id == SAP2.subscription_instance_id)
            .join(Vlan2InstanceValue, Vlan2InstanceValue.subscription_instance_id == SAP2.subscription_instance_id)
            .join(ProductTable)
            .filter(
                and_(
                    Port1InstanceValue.value == str(port_subscription_id_1),
                    Vlan1InstanceValue.value == str(vlan_1),
                    Port2InstanceValue.value == str(port_subscription_id_2),
                    Vlan2InstanceValue.value == str(vlan_2),
                    ProductTable.product_type == "LightPath",
                    or_(ProductTable.tag == "LP", ProductTable.tag == "LPNL"),
                    SubscriptionTable.status == "active",
                ),
            )
        ).one_or_none()
        if not subscription:
            raise_status(HTTPStatus.NOT_FOUND, "Combination not found")

    except MultipleResultsFound:
        logger.exception(
            "Multiple subscriptions found for query with following keys",
            port_subscription_id_1=port_subscription_id_1,
            vlan_1=vlan_1,
            port_subscription_id_2=port_subscription_id_2,
            vlan_2=vlan_2,
        )
        raise_status(HTTPStatus.INTERNAL_SERVER_ERROR, detail="Multiple records found")

    return {"subscription_id": subscription.subscription_id}


@router.get("/{subscription_id}", response_model=SubscriptionDetailsSchema)
def subscription_details_by_id(subscription_id: UUID) -> Optional[SubscriptionTable]:
    subscription = get_subscription_details_by_id(subscription_id)
    if not subscription:
        raise_status(HTTPStatus.NOT_FOUND)
    return subscription


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


@router.get("/tag/{tags}", response_model=List[SubscriptionWithPortAttrSchema])
@router.get("/tag/{tags}/{statuses}", response_model=List[SubscriptionWithPortAttrSchema])
def subscriptions_by_tags(tags: str, statuses: Optional[str] = None) -> List[SubscriptionTable]:
    """Return subscriptions by product tags and optionally subscription statuses.

    Args:
        tags: Comma separated string of product tags
        statuses: comma separated string of subscriptions statuses

    Returns:
        List of subscriptions

    """
    query = (
        SubscriptionTable.query.join(ProductTable)
        .options(undefer(SubscriptionTable.name), undefer(SubscriptionTable.tag), undefer(SubscriptionTable.port_mode))
        .filter(ProductTable.tag.in_(list(map(lambda x: x.strip(), tags.split(",")))))
    )
    if statuses is not None:
        query = query.filter(SubscriptionTable.status.in_(list(map(lambda x: x.strip(), statuses.split(",")))))
    return query.all()


@router.get("/product/{product_id}", response_model=List[SubscriptionWithPortAttrSchema])
def subscriptions_by_product(product_id: UUID) -> List[SubscriptionTable]:
    return (
        SubscriptionTable.query.join(ProductTable)
        .options(undefer(SubscriptionTable.name), undefer(SubscriptionTable.tag), undefer(SubscriptionTable.port_mode))
        .filter(ProductTable.product_id == product_id)
        .filter(SubscriptionTable.status == "active")
        .all()
    )


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
