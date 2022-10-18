from typing import Any, Dict, List, Set, Type, Union

from more_itertools import flatten
from sqlalchemy.orm import Query
from sqlalchemy.sql.expression import Delete, Insert

from orchestrator.cli.domain_gen_helpers.helpers import get_user_input, sql_compile
from orchestrator.cli.domain_gen_helpers.types import DomainModelChanges
from orchestrator.db.models import ProductBlockRelationTable, ProductBlockTable, SubscriptionInstanceTable
from orchestrator.domain.base import ProductBlockModel, get_depends_on_product_block_type_list


def get_product_block_id(block_name: str) -> Query:
    return get_product_block_ids([block_name])


def get_product_block_ids(block_names: Union[List[str], Set[str]]) -> Query:
    return (
        ProductBlockTable.query.where(ProductBlockTable.name.in_(block_names))
        .with_entities(ProductBlockTable.product_block_id)
        .scalar_subquery()
    )


def map_create_product_blocks(product_blocks: Dict[str, Type[ProductBlockModel]]) -> Dict[str, Type[ProductBlockModel]]:
    """Map product blocks to create.

    Args:
        - product_blocks: Dict of product blocks mapped by product block name.

    Returns: Dict of product blocks by product block name to create.
    """
    existing_product_blocks = ProductBlockTable.query.with_entities(ProductBlockTable.name).all()
    existing_product_blocks = [block_name[0] for block_name in existing_product_blocks]
    return {
        block_name: block for block_name, block in product_blocks.items() if block_name not in existing_product_blocks
    }


def map_delete_product_blocks(product_blocks: Dict[str, Type[ProductBlockModel]]) -> List[str]:
    """Map product blocks to delete.

    Args:
        - product_blocks: Dict of product blocks mapped by product block name.

    Returns: List of product block names to delete.
    """
    existing_product_blocks = ProductBlockTable.query.with_entities(ProductBlockTable.name).all()
    return [name[0] for name in existing_product_blocks if name[0] not in product_blocks]


def map_product_block_additional_relations(changes: DomainModelChanges) -> DomainModelChanges:
    """Map additional relations for created product blocks.

    Adds resource type and product block relations.

    Args:
        - changes: DomainModelChanges class with all changes.

    Returns: Updated DomainModelChanges.
    """

    for block_name, block_class in changes.create_product_blocks.items():
        for field_name in block_class._non_product_block_fields_.keys():
            if field_name not in changes.create_resource_type_relations:
                changes.create_resource_type_relations[field_name] = set()
            changes.create_resource_type_relations[field_name].add(block_name)

        product_blocks_in_model = block_class._get_depends_on_product_block_types()
        product_blocks_types_in_model = get_depends_on_product_block_type_list(product_blocks_in_model)
        for product_block in product_blocks_types_in_model:
            depends_on_block_name = product_block.name
            if depends_on_block_name not in changes.create_product_block_relations:
                changes.create_product_block_relations[depends_on_block_name] = set()
            changes.create_product_block_relations[depends_on_block_name].add(block_name)
    return changes


def generate_create_product_blocks_sql(
    create_product_blocks: Dict[str, Any], inputs: Dict[str, Dict[str, str]]
) -> List[str]:
    """Generate SQL to create product blocks.

    Args:
        - create_product_blocks: List of product block names.
        - inputs: Optional Dict to prefill 'description' and 'tag' per product block.
            - key: product block name.
            - value: Dict with 'description' and 'tag'.
                - key: product block property.
                - value: value for the property.

    Returns: List of SQL to create product blocks.
    """

    def create_product_block(name: str) -> str:
        print(f"--- PRODUCT BLOCK ['{name}'] INPUTS ---")  # noqa: T001, T201
        prefilled_values = inputs.get(name, {})
        description = prefilled_values.get("description") or get_user_input("Product block description: ")
        tag = prefilled_values.get("tag") or get_user_input("Product block tag: ")
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


def generate_delete_product_blocks_sql(delete_product_blocks: List[str]) -> List[str]:
    """Generate SQL to delete product blocks.

    Args:
        - delete_product_blocks: List of product block names.

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


def generate_create_product_block_relations_sql(create_block_relations: Dict[str, Set[str]]) -> List[str]:
    """Generate SQL to create product block to product block relations.

    Args:
        - create_block_relations: Dict with product blocks by product block
            - key: product block name.
            - value: Set of product block names to relate with.

    Returns: List of SQL to create relation between product blocks.
    """

    def create_block_relation(depends_block_name: str, block_names: Set[str]) -> str:
        depends_block_id_sql = get_product_block_id(depends_block_name)

        def create_block_relation_dict(block_name: str) -> Dict[str, Query]:
            block_id_sql = get_product_block_id(block_name)
            return {"in_use_by_id": block_id_sql, "depends_on_id": depends_block_id_sql}

        product_product_block_relation_dicts = [create_block_relation_dict(block_name) for block_name in block_names]
        return sql_compile(Insert(ProductBlockRelationTable).values(product_product_block_relation_dicts))

    return [create_block_relation(*item) for item in create_block_relations.items()]


def generate_create_product_block_instance_relations_sql(product_block_relations: Dict[str, Set[str]]) -> List[str]:
    """Generate SQL to create resource type instance values for existing instances.

    Args:
        - product_block_relations: Dict with product blocks by resource type
            - key: product block name.
            - value: Set of product block names to relate to.

    Returns: .
    """

    def create_subscription_instance_relations(depends_block_name: str, block_names: Set[str]) -> List[str]:
        depends_block_id_sql = get_product_block_id(depends_block_name)

        def map_subscription_instances(block_name: str) -> List[Dict[str, Union[str, Query]]]:
            in_use_by_id_sql = get_product_block_id(block_name)
            subscription_ids: list[SubscriptionInstanceTable] = (
                SubscriptionInstanceTable.query.where(SubscriptionInstanceTable.product_block_id.in_(in_use_by_id_sql))
                .with_entities(SubscriptionInstanceTable.subscription_id)
                .all()
            )
            if not subscription_ids:
                return []
            return [
                {"subscription_id": subscription_instance.subscription_id, "product_block_id": in_use_by_id_sql}
                for subscription_instance in subscription_ids
            ]

        def map_subscription_instance_relations(block_name: str) -> List[Dict[str, Union[str, Query]]]:
            block_id_sql = get_product_block_id(block_name)
            subscription_instance_ids: list[SubscriptionInstanceTable] = (
                SubscriptionInstanceTable.query.where(SubscriptionInstanceTable.product_block_id.in_(block_id_sql))
                .with_entities(SubscriptionInstanceTable.subscription_instance_id)
                .all()
            )
            if not subscription_instance_ids:
                return []
            return [
                {"in_use_by_id": instance_id.subscription_instance_id, "depends_on_id": depends_block_id_sql}
                for instance_id in subscription_instance_ids
            ]

        subscription_instance_dicts = list(
            flatten([map_subscription_instances(block_name) for block_name in block_names])
        )
        subscription_relation_dicts = list(
            flatten([map_subscription_instance_relations(block_name) for block_name in block_names])
        )

        subscription_instances = ""
        if subscription_relation_dicts:
            subscription_instances = sql_compile(Insert(SubscriptionInstanceTable).values(subscription_instance_dicts))

        subscription_block_relations = ""
        if subscription_relation_dicts:
            subscription_block_relations = sql_compile(
                Insert(SubscriptionInstanceTable).values(subscription_instance_dicts)
            )
        return [subscription_instances, subscription_block_relations]

    rt_relations = flatten(create_subscription_instance_relations(*item) for item in product_block_relations.items())
    return [rt_relation for rt_relation in rt_relations if rt_relation]


def generate_delete_product_block_relations_sql(delete_block_relations: Dict[str, Set[str]]) -> List[str]:
    """Generate SQL to delete product block to product blocks relations.

    Args:
        - delete_block_relations: Dict with product blocks by product block
            - key: Product block name.
            - value: Set of product block names to relate with.

    Returns: List of SQL to delete relations between product blocks.
    """

    def delete_block_relation(delete_block_name: str, block_names: Set[str]) -> str:
        in_use_by_ids_sql = get_product_block_ids(block_names)
        delete_block_id_sql = get_product_block_id(delete_block_name)
        return sql_compile(
            Delete(ProductBlockRelationTable).where(
                ProductBlockRelationTable.in_use_by_id.in_(in_use_by_ids_sql),
                ProductBlockRelationTable.depends_on_id.in_(delete_block_id_sql),
            )
        )

    return [delete_block_relation(*item) for item in delete_block_relations.items()]
