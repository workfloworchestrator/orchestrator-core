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
from uuid import UUID

from fastapi.routing import APIRouter
from pytz import timezone
from sqlalchemy import select

from orchestrator.api.models import delete
from orchestrator.db import SubscriptionCustomerDescriptionTable, db
from orchestrator.utils.redis import delete_subscription_from_redis
from orchestrator.websocket import invalidate_subscription_cache

router = APIRouter()


def get_customer_description_by_customer_subscription(
    customer_id: str, subscription_id: UUID
) -> SubscriptionCustomerDescriptionTable | None:
    stmt = select(SubscriptionCustomerDescriptionTable).filter(
        SubscriptionCustomerDescriptionTable.customer_id == customer_id,
        SubscriptionCustomerDescriptionTable.subscription_id == str(subscription_id),
    )
    return db.session.scalars(stmt).one_or_none()


@delete_subscription_from_redis()
async def create_subscription_customer_description(
    customer_id: str, subscription_id: UUID, description: str
) -> SubscriptionCustomerDescriptionTable:
    customer_description = SubscriptionCustomerDescriptionTable(
        customer_id=customer_id,
        subscription_id=subscription_id,
        description=description,
    )
    db.session.add(customer_description)
    db.session.commit()
    await invalidate_subscription_cache(customer_description.subscription_id)
    return customer_description


@delete_subscription_from_redis()
async def update_subscription_customer_description(
    customer_description: SubscriptionCustomerDescriptionTable, description: str, created_at: datetime | None = None
) -> SubscriptionCustomerDescriptionTable:
    customer_description.description = description
    customer_description.created_at = created_at if created_at else datetime.now(tz=timezone("UTC"))
    db.session.commit()
    await invalidate_subscription_cache(customer_description.subscription_id)
    return customer_description


@delete_subscription_from_redis()
async def delete_subscription_customer_description_by_customer_subscription(
    customer_id: str, subscription_id: UUID
) -> SubscriptionCustomerDescriptionTable | None:
    customer_description = get_customer_description_by_customer_subscription(customer_id, subscription_id)
    if not customer_description:
        return None

    delete(SubscriptionCustomerDescriptionTable, customer_description.id)
    await invalidate_subscription_cache(customer_description.subscription_id)
    return customer_description
