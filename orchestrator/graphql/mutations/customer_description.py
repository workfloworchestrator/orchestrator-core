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
from uuid import UUID

import strawberry
import structlog

from oauth2_lib.strawberry import authenticated_mutation_field
from orchestrator.db.models import SubscriptionCustomerDescriptionTable
from orchestrator.domain.customer_description import (
    create_subscription_customer_description,
    delete_subscription_customer_description_by_customer_subscription,
    get_customer_description_by_customer_subscription,
    update_subscription_customer_description,
)
from orchestrator.graphql.schemas.customer_description import CustomerDescription
from orchestrator.graphql.types import MutationError, NotFoundError

logger = structlog.get_logger(__name__)


async def upsert_customer_description(
    customer_id: str, subscription_id: UUID, description: str
) -> SubscriptionCustomerDescriptionTable | NotFoundError:
    current_description = get_customer_description_by_customer_subscription(customer_id, subscription_id)

    if current_description:
        return await update_subscription_customer_description(current_description, description)
    return await create_subscription_customer_description(customer_id, subscription_id, description)


async def resolve_upsert_customer_description(
    customer_id: str, subscription_id: UUID, description: str
) -> CustomerDescription | NotFoundError | MutationError:
    try:
        customer_description = await upsert_customer_description(customer_id, subscription_id, description)
    except Exception:
        return NotFoundError(message="Subscription not found")
    return CustomerDescription.from_pydantic(customer_description)  # type: ignore


async def resolve_remove_customer_description(
    customer_id: str, subscription_id: UUID
) -> CustomerDescription | NotFoundError | MutationError:
    description = await delete_subscription_customer_description_by_customer_subscription(
        customer_id=customer_id, subscription_id=subscription_id
    )
    if not description:
        return NotFoundError(message="Customer description not found")
    return CustomerDescription.from_pydantic(description)


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
