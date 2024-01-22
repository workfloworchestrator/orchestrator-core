from collections.abc import Generator
from itertools import chain
from typing import Any

from more_itertools import flatten
from sqlalchemy import select
from sqlalchemy.sql.expression import Delete, Insert
from sqlalchemy.sql.selectable import ScalarSelect

from orchestrator.cli.domain_gen_helpers.helpers import get_product_block_names, sql_compile
from orchestrator.cli.domain_gen_helpers.types import DomainModelChanges
from orchestrator.cli.helpers.input_helpers import get_user_input
from orchestrator.cli.helpers.print_helpers import COLOR, print_fmt, str_fmt
from orchestrator.db import db
from orchestrator.db.models import (
    ProductBlockRelationTable,
    ProductBlockTable,
    SubscriptionInstanceRelationTable,
    SubscriptionInstanceTable,
)
from orchestrator.domain.base import ProductBlockModel, get_depends_on_product_block_type_list


def get_product_block_id(block_name: str) -> ScalarSelect:
    return get_product_block_ids([block_name])


def get_product_block_ids(block_names: list[str] | set[str]) -> ScalarSelect:
    return select(ProductBlockTable.product_block_id).where(ProductBlockTable.name.in_(block_names)).scalar_subquery()


def get_subscription_instance(subscription_id: str, product_block_id: ScalarSelect) -> ScalarSelect:
    return (
        select(SubscriptionInstanceTable.subscription_instance_id)
        .where(
            SubscriptionInstanceTable.product_block_id.in_(product_block_id),
            SubscriptionInstanceTable.subscription_id == subscription_id,
        )
        .limit(1)
        .as_scalar()
    )


def map_create_product_blocks(product_blocks: dict[str, type[ProductBlockModel]]) -> dict[str, type[ProductBlockModel]]:
    """Map product blocks to create.

    Args:
        product_blocks: Dict of product blocks mapped by product block name.

    Returns: Dict of product blocks by product block name to create.
    """
    _existing_product_blocks = db.session.scalars(select(ProductBlockTable.name))
    existing_product_blocks = set(_existing_product_blocks)
    return {
        block_name: block for block_name, block in product_blocks.items() if block_name not in existing_product_blocks
    }


def map_delete_product_blocks(product_blocks: dict[str, type[ProductBlockModel]]) -> set[str]:
    """Map product blocks to delete.

    Args:
        product_blocks: Dict of product blocks mapped by product block name.

    Returns: List of product block names to delete.
    """
    existing_product_blocks = db.session.scalars(select(ProductBlockTable.name))
    return {name for name in existing_product_blocks if name not in product_blocks}


def map_product_block_additional_relations(changes: DomainModelChanges) -> DomainModelChanges:
    """Map additional relations for created product blocks.

    Adds resource type and product block relations.

    Args:
        changes: DomainModelChanges class with all changes.

    Returns: Updated DomainModelChanges.
    """

    for block_name, block_class in changes.create_product_blocks.items():
        for field_name in block_class._non_product_block_fields_.keys():
            changes.create_resource_type_relations.setdefault(field_name, set()).add(block_name)

        product_blocks_in_model = block_class._get_depends_on_product_block_types()
        product_blocks_types_in_model = get_depends_on_product_block_type_list(product_blocks_in_model)
        for product_block_name in get_product_block_names(product_blocks_types_in_model):
            changes.create_product_block_relations.setdefault(product_block_name, set()).add(block_name)
    return changes


def generate_create_product_blocks_sql(
    create_product_blocks: dict[str, Any], inputs: dict[str, dict[str, str]]
) -> list[str]:
    """Generate SQL to create product blocks.

    Args:
        create_product_blocks: List of product block names.
        inputs: Optional Dict to prefill 'description' and 'tag' per product block.
            - key: product block name.
            - value: Dict with 'description' and 'tag'.
                - key: product block property.
                - value: value for the property.

    Returns: List of SQL to create product blocks.
    """
    print_fmt("\nCreate product blocks", flags=[COLOR.BOLD, COLOR.UNDERLINE])

    def create_product_block(name: str) -> str:
        print(f"Product block: {str_fmt(name, flags=[COLOR.BOLD])}")  # noqa: T001, T201
        prefilled_values = inputs.get(name, {})
        description = prefilled_values.get("description") or get_user_input("Supply the product block description: ")
        tag = prefilled_values.get("tag") or get_user_input("Supply the product block tag: ")
        return sql_compile(
            Insert(ProductBlockTable).values(
                {
                    "name": name,
                    "description": description,
                    "tag": tag,
                    "status": "active",
                }
            )
        )

    return [create_product_block(name) for name in create_product_blocks]


def generate_delete_product_blocks_sql(delete_product_blocks: set[str]) -> list[str]:
    """Generate SQL to delete product blocks.

    Args:
        delete_product_blocks: List of product block names.

    Returns: List of SQL to delete product blocks.
    """

    if not delete_product_blocks:
        return []
    return [
        sql_compile(
            Delete(SubscriptionInstanceTable).where(
                SubscriptionInstanceTable.product_block_id.in_(get_product_block_ids(delete_product_blocks))
            )
        ),
        sql_compile(Delete(ProductBlockTable).where(ProductBlockTable.name.in_(delete_product_blocks))),
    ]


def generate_create_product_block_relations_sql(create_block_relations: dict[str, set[str]]) -> list[str]:
    """Generate SQL to create product block to product block relations.

    Args:
        create_block_relations: Dict with product blocks by product block
            - key: product block name.
            - value: Set of product block names to relate with.

    Returns: List of SQL to create relation between product blocks.
    """

    def create_block_relation(depends_block_name: str, block_names: set[str]) -> str:
        depends_block_id_sql = get_product_block_id(depends_block_name)

        def create_block_relation_dict(block_name: str) -> dict[str, ScalarSelect]:
            block_id_sql = get_product_block_id(block_name)
            return {"in_use_by_id": block_id_sql, "depends_on_id": depends_block_id_sql}

        product_product_block_relation_dicts = [create_block_relation_dict(block_name) for block_name in block_names]
        return sql_compile(Insert(ProductBlockRelationTable).values(product_product_block_relation_dicts))

    return [create_block_relation(*item) for item in create_block_relations.items()]


def generate_create_product_block_instance_relations_sql(product_block_relations: dict[str, set[str]]) -> list[str]:
    """Generate SQL to create resource type instance values for existing instances.

    Args:
        product_block_relations: Dict with product blocks by resource type
            - key: product block name.
            - value: Set of product block names to relate to.

    Returns: .
    """

    def create_subscription_instance_relations(
        depends_block_name: str, block_names: set[str]
    ) -> Generator[str, None, None]:
        depends_block_id_sql = get_product_block_id(depends_block_name)

        def map_subscription_instances(block_name: str) -> dict[str, list[dict[str, str | ScalarSelect]]]:
            in_use_by_id_sql = get_product_block_id(block_name)
            stmt = select(
                SubscriptionInstanceTable.subscription_instance_id, SubscriptionInstanceTable.subscription_id
            ).where(SubscriptionInstanceTable.product_block_id.in_(in_use_by_id_sql))

            subscription_instances = list(db.session.execute(stmt))
            if not subscription_instances:
                subscription_instances = []

            instance_list = [
                {"subscription_id": subscription_id, "product_block_id": depends_block_id_sql}
                for instance_id, subscription_id, in subscription_instances
            ]
            instance_relation_list = [
                {
                    "in_use_by_id": instance.subscription_instance_id,
                    "depends_on_id": get_subscription_instance(instance.subscription_id, depends_block_id_sql),
                    "order_id": 0,
                }
                for instance in subscription_instances
            ]

            return {"instance_list": instance_list, "instance_relation_list": instance_relation_list}

        create_instance_list = [map_subscription_instances(block_name) for block_name in block_names]

        subscription_instance_dicts = list(flatten(item["instance_list"] for item in create_instance_list))
        subscription_relation_dicts = list(flatten(item["instance_relation_list"] for item in create_instance_list))

        if subscription_instance_dicts:
            yield sql_compile(Insert(SubscriptionInstanceTable).values(subscription_instance_dicts))

        if subscription_relation_dicts:
            yield sql_compile(Insert(SubscriptionInstanceRelationTable).values(subscription_relation_dicts))

    return list(
        chain.from_iterable(create_subscription_instance_relations(*item) for item in product_block_relations.items())
    )


def generate_delete_product_block_relations_sql(delete_block_relations: dict[str, set[str]]) -> list[str]:
    """Generate SQL to delete product block to product blocks relations.

    Args:
        delete_block_relations: Dict with product blocks by product block
            - key: Product block name.
            - value: Set of product block names to relate with.

    Returns: List of SQL to delete relations between product blocks.
    """

    def delete_block_relation(delete_block_name: str, block_names: set[str]) -> str:
        in_use_by_ids_sql = get_product_block_ids(block_names)
        delete_block_id_sql = get_product_block_id(delete_block_name)

        return sql_compile(
            Delete(ProductBlockRelationTable).where(
                ProductBlockRelationTable.in_use_by_id.in_(in_use_by_ids_sql),
                ProductBlockRelationTable.depends_on_id.in_(delete_block_id_sql),
            )
        )

    return [delete_block_relation(*item) for item in delete_block_relations.items()]
