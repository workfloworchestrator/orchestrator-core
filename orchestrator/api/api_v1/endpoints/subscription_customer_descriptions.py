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

from datetime import datetime
from http import HTTPStatus
from uuid import UUID

from fastapi.param_functions import Body
from fastapi.routing import APIRouter
from pytz import timezone

from orchestrator.api.error_handling import raise_status
from orchestrator.api.models import delete, save, update
from orchestrator.db import SubscriptionCustomerDescriptionTable
from orchestrator.schemas import SubscriptionDescriptionBaseSchema, SubscriptionDescriptionSchema
from orchestrator.utils.redis import delete_from_redis

router = APIRouter()


@router.post("/", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def save_subscription_customer_description(data: SubscriptionDescriptionBaseSchema = Body(...)) -> None:
    save(SubscriptionCustomerDescriptionTable, data)
    delete_from_redis(data.subscription_id)


@router.put("/", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def update_subscription_customer_descriptions(data: SubscriptionDescriptionSchema = Body(...)) -> None:
    if data.created_at is None:
        data.created_at = datetime.now(tz=timezone("UTC"))
    update(SubscriptionCustomerDescriptionTable, data)
    delete_from_redis(data.subscription_id)


@router.delete("/{_id}", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def delete_subscription_customer_descriptions(_id: UUID) -> None:
    description = SubscriptionCustomerDescriptionTable.query.get(_id)
    delete(SubscriptionCustomerDescriptionTable, _id)
    delete_from_redis(description.subscription_id)


@router.get("/{_id}", response_model=SubscriptionDescriptionSchema)
def get_subscription_customer_descriptions(_id: UUID) -> str:
    description = SubscriptionCustomerDescriptionTable.query.get(_id)
    if description is None:
        raise_status(HTTPStatus.NOT_FOUND)
    return description


@router.get("/customer/{customer_id}/subscription/{subscription_id}", response_model=SubscriptionDescriptionSchema)
def get_subscription_customer_description_by_customer_subscription(customer_id: UUID, subscription_id: UUID) -> str:
    description = SubscriptionCustomerDescriptionTable.query.filter_by(
        customer_id=customer_id, subscription_id=subscription_id
    ).one_or_none()
    if description is None:
        raise_status(HTTPStatus.NOT_FOUND)
    return description
