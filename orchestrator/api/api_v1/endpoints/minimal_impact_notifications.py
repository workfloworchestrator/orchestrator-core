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
from typing import List
from uuid import UUID

from fastapi.param_functions import Body
from fastapi.routing import APIRouter

from orchestrator.api.error_handling import raise_status
from orchestrator.api.models import delete, save, update
from orchestrator.db import MinimalImpactNotificationTable
from orchestrator.schemas import MinimalImpactNotificationBaseSchema, MinimalImpactNotificationSchema

router = APIRouter()


@router.post("/", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def save_minimal_impact_notification(data: MinimalImpactNotificationBaseSchema = Body(...)) -> None:
    return save(MinimalImpactNotificationTable, data)


@router.put("/", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def update_minimal_impact_notification(data: MinimalImpactNotificationSchema = Body(...)) -> None:
    return update(MinimalImpactNotificationTable, data)


@router.delete("/{_id}", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def delete_minimal_impact_notification(_id: UUID) -> None:
    return delete(MinimalImpactNotificationTable, _id)


@router.get("/{_id}", response_model=MinimalImpactNotificationSchema)
def get_minimal_impact_notification(_id: UUID) -> str:
    minimal_impact_notification = MinimalImpactNotificationTable.query.get(_id)
    if minimal_impact_notification is None:
        raise_status(HTTPStatus.NOT_FOUND)
    return minimal_impact_notification


@router.get("/customer/{customer_id}", response_model=List[MinimalImpactNotificationSchema])
def get_minimal_impact_notifications_by_customer_id(customer_id: UUID) -> str:
    minimal_impact_notification = MinimalImpactNotificationTable.query.filter_by(customer_id=customer_id).all()
    if not minimal_impact_notification:
        raise_status(HTTPStatus.NOT_FOUND)
    return minimal_impact_notification


@router.get("/customer/{customer_id}/subscription/{subscription_id}", response_model=MinimalImpactNotificationSchema)
def get_minimal_impact_notification_by_customer_subscription(customer_id: UUID, subscription_id: UUID) -> str:
    minimal_impact_notification = MinimalImpactNotificationTable.query.filter_by(
        customer_id=customer_id, subscription_id=subscription_id
    ).one_or_none()
    if minimal_impact_notification is None:
        raise_status(HTTPStatus.NOT_FOUND)
    return minimal_impact_notification
