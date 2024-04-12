# Copyright 2022-2024 SURF.
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

import strawberry
import structlog
from pytz import timezone
from sqlalchemy import select

from oauth2_lib.strawberry import authenticated_mutation_field
from orchestrator.api.models import delete
from orchestrator.db import SubscriptionCustomerDescriptionTable, db
from orchestrator.graphql.schemas.customer_description import CustomerDescription
from orchestrator.graphql.types import MutationError, NotFound
from orchestrator.utils.redis import delete_from_redis

logger = structlog.get_logger(__name__)


def get_customer_description(customer_id: UUID, subscription_id: UUID) -> SubscriptionCustomerDescriptionTable | None:
    stmt = select(SubscriptionCustomerDescriptionTable).filter(
        SubscriptionCustomerDescriptionTable.customer_id == str(customer_id),
        SubscriptionCustomerDescriptionTable.subscription_id == str(subscription_id),
    )
    return db.session.scalars(stmt).one_or_none()


def create_customer_description(
    customer_id: UUID, subscription_id: UUID, description: str
) -> CustomerDescription | NotFound:
    customer_description = SubscriptionCustomerDescriptionTable(
        customer_id=customer_id,
        subscription_id=subscription_id,
        description=description,
    )
    db.session.add(customer_description)

    try:
        db.session.commit()
    except Exception:
        return NotFound(message="Subscription not found")

    delete_from_redis(subscription_id)
    return CustomerDescription.from_pydantic(customer_description)


def update_customer_description(
    subscription_id: UUID,
    description: str,
    current_description: SubscriptionCustomerDescriptionTable,
) -> CustomerDescription:
    current_description.description = description
    current_description.created_at = datetime.now(tz=timezone("UTC"))
    db.session.commit()
    delete_from_redis(subscription_id)
    return CustomerDescription.from_pydantic(current_description)  # type: ignore


async def resolve_upsert_customer_description(
    customer_id: UUID, subscription_id: UUID, description: str
) -> CustomerDescription | NotFound | MutationError:
    current_description = get_customer_description(customer_id, subscription_id)

    if current_description:
        return update_customer_description(subscription_id, description, current_description)
    return create_customer_description(customer_id, subscription_id, description)


async def resolve_remove_customer_description(
    customer_id: UUID, subscription_id: UUID
) -> CustomerDescription | NotFound | MutationError:
    description = get_customer_description(customer_id, subscription_id)
    if not description:
        return NotFound(message="Customer description not found")

    delete(SubscriptionCustomerDescriptionTable, description.id)
    delete_from_redis(subscription_id)
    return CustomerDescription.from_pydantic(description)  # type: ignore


@strawberry.type(description="Customer subscription description mutations")
class CustomerSubscriptionDescriptionMutation:
    upsert_customer_description = authenticated_mutation_field(
        resolver=resolve_upsert_customer_description,
        description="Create or update customer description",
    )
    remove_customer_description = authenticated_mutation_field(
        resolver=resolve_remove_customer_description,
        description="Delete customer description",
    )
