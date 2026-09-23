# Copyright 2019-2026 SURF, GÉANT.
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
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.api.models import delete_async
from orchestrator.core.db import SubscriptionCustomerDescriptionTable
from orchestrator.core.utils.errors import StaleDataError
from orchestrator.core.utils.validate_data_version import validate_data_version
from orchestrator.core.websocket import invalidate_subscription_cache

router = APIRouter()


async def get_customer_description_by_customer_subscription(
    customer_id: str, subscription_id: UUID, session: AsyncSession
) -> SubscriptionCustomerDescriptionTable | None:
    stmt = select(SubscriptionCustomerDescriptionTable).filter(
        SubscriptionCustomerDescriptionTable.customer_id == customer_id,
        SubscriptionCustomerDescriptionTable.subscription_id == str(subscription_id),
    )
    result = await session.scalars(stmt)
    return result.one_or_none()


async def create_subscription_customer_description(
    customer_id: str, subscription_id: UUID, description: str, session: AsyncSession
) -> SubscriptionCustomerDescriptionTable:
    customer_description = SubscriptionCustomerDescriptionTable(
        customer_id=customer_id,
        subscription_id=subscription_id,
        description=description,
    )
    session.add(customer_description)
    await session.commit()
    await invalidate_subscription_cache(customer_description.subscription_id)
    return customer_description


async def update_subscription_customer_description(
    customer_description: SubscriptionCustomerDescriptionTable,
    description: str,
    session: AsyncSession,
    created_at: datetime | None = None,
    version: int | None = None,
) -> SubscriptionCustomerDescriptionTable:
    if not validate_data_version(customer_description.version, version):
        raise StaleDataError(customer_description.version, version)

    customer_description.description = description
    customer_description.created_at = created_at if created_at else datetime.now(tz=timezone("UTC"))
    await session.commit()
    # Refresh the version incremented by the database trigger.
    await session.refresh(customer_description, attribute_names=["version"])
    await invalidate_subscription_cache(customer_description.subscription_id)
    return customer_description


async def delete_subscription_customer_description_by_customer_subscription(
    customer_id: str, subscription_id: UUID, session: AsyncSession,
) -> SubscriptionCustomerDescriptionTable | None:
    customer_description = await get_customer_description_by_customer_subscription(customer_id, subscription_id, session)
    if not customer_description:
        return None

    await delete_async(SubscriptionCustomerDescriptionTable, customer_description.id, session)
    await invalidate_subscription_cache(customer_description.subscription_id)
    return customer_description
