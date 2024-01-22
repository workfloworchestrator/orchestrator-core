import random
import string
from typing import Any

from orchestrator.db import (
    ProductTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    SubscriptionTable,
    db,
)
from orchestrator.utils.datetime import nowtz
from pydantic_forms.types import SubscriptionMapping


def randomstr(length=3):
    charset = string.ascii_lowercase + string.digits
    return "".join(random.choice(charset) for _ in range(0, length))  # noqa: S311


def create_subscription_for_mapping(
    product: ProductTable, mapping: SubscriptionMapping, values: dict[str, Any], **kwargs: Any
) -> SubscriptionTable:
    """Create a subscription in the test coredb for the given subscription_mapping and values.

    This function handles optional resource types starting with a ? in the mapping not supplied in the values array.

    Args:
        product: the ProductTable to create a sub for
        mapping: the subscription_mapping belonging to that product
        values: a dictionary of keys from the sub_map and their corresponding test values
        kwargs: The rest of the arguments

    Returns: The conforming subscription.
    """

    def build_instance(name, value_mapping):
        block = product.find_block_by_name(name)

        def build_value(rt, value):
            resource_type = block.find_resource_type_by_name(rt)
            return SubscriptionInstanceValueTable(resource_type_id=resource_type.resource_type_id, value=value)

        return SubscriptionInstanceTable(
            product_block_id=block.product_block_id,
            values=[
                build_value(resource_type, values[value_key]) for (resource_type, value_key) in value_mapping.items()
            ],
        )

    # recreate the mapping: leave out the ?keys if no value supplied for them
    mapping = {
        name: [
            {
                **{k: value_map[k] for k in value_map if not value_map[k].startswith("?")},
                **{
                    k: value_map[k][1:]
                    for k in value_map
                    if value_map[k].startswith("?") and value_map[k][1:] in values
                },
            }
            for value_map in mapping[name]
        ]
        for name in mapping
    }

    instances = [
        build_instance(name, value_mapping)
        for (name, value_mappings) in mapping.items()
        for value_mapping in value_mappings
    ]

    return create_subscription(instances=instances, product=product, **kwargs)


def create_subscription(**kwargs):
    attrs = {
        "description": "A subscription.",
        "customer_id": "85938c4c-0a11-e511-80d0-005056956c1a",
        "start_date": nowtz(),
        "status": "active",
        "insync": True,
        **kwargs,
    }
    o = SubscriptionTable(**attrs)
    db.session.add(o)
    db.session.commit()
    return o
