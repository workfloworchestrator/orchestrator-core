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

from http import HTTPStatus
from uuid import UUID

from fastapi.param_functions import Body
from fastapi.routing import APIRouter

from orchestrator.api.error_handling import raise_status
from orchestrator.api.models import delete
from orchestrator.db import SubscriptionCustomerDescriptionTable, db
from orchestrator.domain.customer_description import (
    create_subscription_customer_description,
    get_customer_description_by_customer_subscription,
    update_subscription_customer_description,
)
from orchestrator.schemas import SubscriptionDescriptionBaseSchema, SubscriptionDescriptionSchema
from orchestrator.utils.redis import delete_from_redis

router = APIRouter()


@router.post("/", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def save_subscription_customer_description_endpoint(data: SubscriptionDescriptionBaseSchema = Body(...)) -> None:
    create_subscription_customer_description(data.customer_id, data.subscription_id, data.description)


@router.put("/", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def update_subscription_customer_description_endpoint(data: SubscriptionDescriptionSchema = Body(...)) -> None:
    description = get_customer_description_by_customer_subscription(data.customer_id, data.subscription_id)
    if description:
        update_subscription_customer_description(description, data.description, data.created_at)


@router.delete("/{_id}", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def delete_subscription_customer_descriptions(_id: UUID) -> None:
    description = db.session.get(SubscriptionCustomerDescriptionTable, _id)
    if description:
        delete(SubscriptionCustomerDescriptionTable, _id)
        delete_from_redis(description.subscription_id)


@router.get("/{_id}", response_model=SubscriptionDescriptionSchema)
def get_subscription_customer_descriptions(_id: UUID) -> str:
    description = db.session.get(SubscriptionCustomerDescriptionTable, _id)
    if description is None:
        raise_status(HTTPStatus.NOT_FOUND)
    return description


@router.get("/customer/{customer_id}/subscription/{subscription_id}", response_model=SubscriptionDescriptionSchema)
def get_subscription_customer_description_by_customer_subscription(
    customer_id: str, subscription_id: UUID
) -> SubscriptionCustomerDescriptionTable:
    description = get_customer_description_by_customer_subscription(customer_id, subscription_id)
    if description is None:
        raise_status(HTTPStatus.NOT_FOUND)
    return description
