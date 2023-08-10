from itertools import count
from typing import Any, Generator, Optional
from uuid import UUID

import strawberry
from pydantic.utils import to_lower_camel
from strawberry.scalars import JSON

from orchestrator.domain.base import SubscriptionModel
from orchestrator.services.subscriptions import build_extended_domain_model


@strawberry.type
class ProductBlockInstance:
    id: int
    parent: Optional[int]
    subscription_instance_id: UUID
    owner_subscription_id: UUID
    product_block_instance_values: JSON

    @strawberry.field(description="Returns all resource types of a product block", deprecation_reason="changed to product_block_instance_values")  # type: ignore
    async def resource_types(self) -> JSON:
        return {v["field"]: v["value"] for v in self.product_block_instance_values}


def is_product_block(candidate: Any) -> bool:
    if isinstance(candidate, dict):
        # TODO: also filter on tag (needs addition of tag in orchestrator endpoint)
        # NOTE: this crosses subscription boundaries. If needed we can add an additional filter to limit that.
        return candidate.get("owner_subscription_id", None)
    return False


def get_all_product_blocks(subscription: dict[str, Any], _tags: Optional[list[str]]) -> list[dict[str, Any]]:
    gen_id = count()

    def locate_product_block(candidate: dict[str, Any]) -> Generator:
        def new_product_block(item: dict[str, Any]) -> Generator:
            enriched_item = item | {"id": next(gen_id), "parent": candidate.get("id")}
            yield enriched_item
            yield from locate_product_block(enriched_item)

        for value in candidate.values():
            if is_product_block(value):
                yield from new_product_block(value)
            elif isinstance(value, list):
                for item in value:
                    if is_product_block(item):
                        yield from new_product_block(item)

    return list(locate_product_block(subscription))


async def get_subscription_product_blocks(
    subscription_id: UUID, tags: Optional[list[str]] = None, product_block_instance_values: Optional[list[str]] = None
) -> list[ProductBlockInstance]:
    subscription_model = SubscriptionModel.from_subscription(subscription_id)
    subscription = build_extended_domain_model(subscription_model)

    def to_product_block(product_block: dict[str, Any]) -> ProductBlockInstance:
        def is_resource_type(candidate: Any) -> bool:
            return isinstance(candidate, (bool, str, int, float, type(None)))

        def requested_resource_type(key: str) -> bool:
            return not product_block_instance_values or key in product_block_instance_values

        def included(key: str, value: Any) -> bool:
            return is_resource_type(value) and requested_resource_type(key) and key not in ("id", "parent")

        return ProductBlockInstance(
            id=product_block["id"],
            parent=product_block.get("parent"),
            owner_subscription_id=product_block["owner_subscription_id"],
            subscription_instance_id=product_block["subscription_instance_id"],
            product_block_instance_values=[
                {"field": to_lower_camel(k), "value": v} for k, v in product_block.items() if included(k, v)
            ],
        )

    product_blocks = (to_product_block(product_block) for product_block in get_all_product_blocks(subscription, tags))
    return [product_block for product_block in product_blocks if product_block.product_block_instance_values]
