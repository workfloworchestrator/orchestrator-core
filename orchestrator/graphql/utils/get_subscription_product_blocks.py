from collections.abc import Generator
from itertools import count
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

import strawberry
from pydantic.alias_generators import to_camel as to_lower_camel
from strawberry.scalars import JSON

from orchestrator.graphql.schemas.product_block import owner_subscription_resolver
from orchestrator.utils.get_subscription_dict import get_subscription_dict

if TYPE_CHECKING:
    from orchestrator.graphql.schemas.subscription import SubscriptionInterface


@strawberry.type
class ProductBlockInstance:
    id: int
    parent: int | None
    subscription_instance_id: UUID
    owner_subscription_id: UUID
    in_use_by_relations: list[JSON]
    product_block_instance_values: JSON
    subscription: (
        Annotated["SubscriptionInterface", strawberry.lazy("orchestrator.graphql.schemas.subscription")] | None
    ) = strawberry.field(
        description="resolve to subscription of the product block", resolver=owner_subscription_resolver
    )


def is_product_block(candidate: Any) -> bool:
    if isinstance(candidate, dict):
        # TODO: also filter on tag (needs addition of tag in orchestrator endpoint)
        # NOTE: this crosses subscription boundaries. If needed we can add an additional filter to limit that.
        return candidate.get("owner_subscription_id", None)
    return False


def get_all_product_blocks(subscription: dict[str, Any], _tags: list[str] | None) -> list[dict[str, Any]]:
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


pb_instance_property_keys = ("id", "parent", "owner_subscription_id", "subscription_instance_id", "in_use_by_relations")


async def get_subscription_product_blocks(
    subscription_id: UUID, tags: list[str] | None = None, product_block_instance_values: list[str] | None = None
) -> list[ProductBlockInstance]:
    subscription, _ = await get_subscription_dict(subscription_id)

    def to_product_block(product_block: dict[str, Any]) -> ProductBlockInstance:
        def is_resource_type(candidate: Any) -> bool:
            return not isinstance(candidate, (list, dict))

        def requested_resource_type(key: str) -> bool:
            return not product_block_instance_values or key in product_block_instance_values

        def included(key: str, value: Any) -> bool:
            return is_resource_type(value) and requested_resource_type(key) and key not in pb_instance_property_keys

        return ProductBlockInstance(
            id=product_block["id"],
            parent=product_block.get("parent"),
            owner_subscription_id=product_block["owner_subscription_id"],
            subscription_instance_id=product_block["subscription_instance_id"],
            product_block_instance_values=[
                {"field": to_lower_camel(k), "value": v if isinstance(v, (str, int, float, type(None))) else str(v)}
                for k, v in product_block.items()
                if included(k, v)
            ],
            in_use_by_relations=product_block.get("in_use_by_relations", []),
        )

    product_blocks = (to_product_block(product_block) for product_block in get_all_product_blocks(subscription, tags))
    return [product_block for product_block in product_blocks if product_block.product_block_instance_values]
