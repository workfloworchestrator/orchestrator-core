from itertools import chain
from typing import Dict, Generator, List, Set, Type, Union

from sqlalchemy.orm import Query
from sqlalchemy.sql.expression import Delete, Insert

from orchestrator.cli.domain_gen_helpers.helpers import get_user_input, sql_compile
from orchestrator.cli.domain_gen_helpers.product_block_helpers import get_product_block_id
from orchestrator.cli.domain_gen_helpers.types import DomainModelChanges
from orchestrator.db.models import (
    ProductTable,
    SubscriptionInstanceTable,
    SubscriptionTable,
    product_product_block_association,
)
from orchestrator.domain.base import SubscriptionModel, get_depends_on_product_block_type_list


def get_product_id(product_name: str) -> Query:
    return get_product_ids([product_name])


def get_product_ids(product_names: Union[List[str], Set[str]]) -> Query:
    return (
        ProductTable.query.where(ProductTable.name.in_(product_names))
        .with_entities(ProductTable.product_id)
        .scalar_subquery()
    )


def map_product_additional_relations(changes: DomainModelChanges) -> DomainModelChanges:
    """Map additional relations for created products.

    Adds resource type and product block relations.

    Args:
        - changes: DomainModelChanges class with all changes.

    Returns: Updated DomainModelChanges.
    """

    for product_name, product_class in changes.create_products.items():
        for field_name in product_class._non_product_block_fields_.keys():
            changes.create_product_fixed_inputs.setdefault(field_name, set()).add(product_name)

        product_blocks_in_model = product_class._get_depends_on_product_block_types()
        product_blocks_types_in_model = get_depends_on_product_block_type_list(product_blocks_in_model)
        for product_block in product_blocks_types_in_model:
            changes.create_product_to_block_relations.setdefault(product_block.name, set()).add(product_name)
    return changes


def generate_create_products_sql(
    create_products: Dict[str, Type[SubscriptionModel]], inputs: Dict[str, Dict[str, str]]
) -> List[str]:
    """Generate SQL to create products.

    Args:
        - create_products: Dict of SubscriptionModels by product name.
            - key: product name.
            - value: SubscriptionModel
        - inputs: Optional Dict to add prefilled values for 'description', 'product_type' and 'tag' per product.
            - key: product name.
            - value: Dict with 'description', 'product_type' and 'tag'.
                - key: product property.
                - value: value for the property.

    Returns: List of SQL strings to create products.
    """

    def create_product(name: str) -> str:
        values = inputs.get(name, {})
        print(f"--- PRODUCT ['{name}'] INPUTS ---")  # noqa: T001, T201
        description = values.get("description") or get_user_input("Product description: ")
        product_type = values.get("product_type") or get_user_input("Product type: ")
        tag = values.get("tag") or get_user_input("Product tag: ")
        return sql_compile(
            Insert(ProductTable).values(
                {
                    "name": name,
                    "description": description,
                    "product_type": product_type,
                    "tag": tag,
                    "status": "active",
                }
            )
        )

    return [create_product(name) for name in create_products.keys()]


def generate_delete_products_sql(delete_products: Set[str]) -> List[str]:
    """Generate SQL to delete products.

    Args:
        - delete_products: List of product names.

    Returns: List of SQL strings to delete products.
    """

    def delete_product_block(product_name: str) -> str:
        return sql_compile(Delete(ProductTable).where(ProductTable.name == product_name))

    return [delete_product_block(product_name) for product_name in delete_products]


def generate_create_product_relations_sql(create_block_relations: Dict[str, Set[str]]) -> List[str]:
    """Generate SQL to create product relations to product blocks.

    Args:
        - create_block_relations: Dict with product names by product block
            - key: product block name.
            - value: Set of product names to relate with.

    Returns: List of SQL strings to create subscription instances.
    """

    def create_block_relation(block_name: str, product_names: Set[str]) -> str:
        block_id_sql = get_product_block_id(block_name)

        def create_block_relation_dict(product_name: str) -> Dict[str, Query]:
            product_id_sql = get_product_id(product_name)
            return {"product_block_id": block_id_sql, "product_id": product_id_sql}

        product_product_block_relation_dicts = [
            create_block_relation_dict(product_name) for product_name in product_names
        ]
        return sql_compile(Insert(product_product_block_association).values(product_product_block_relation_dicts))

    return [create_block_relation(*item) for item in create_block_relations.items()]


def generate_create_product_instance_relations_sql(product_to_block_relations: Dict[str, Set[str]]) -> List[str]:
    """Generate SQL to create subscription instances for existing subscriptions.

    Args:
        - product_to_block_relations: Dict with product blocks by resource type
            - key: product block name.
            - value: Set of product names to relate with.

    Returns: List of SQL strings to create subscription instances.
    """

    def create_subscription_instance_relations(block_name: str, product_names: Set[str]) -> Generator[str, None, None]:
        product_block_id = get_product_block_id(block_name)

        def map_subscription_instance_relations(
            product_name: str,
        ) -> Generator[Dict[str, Union[str, Query]], None, None]:
            product_id_sql = get_product_id(product_name)
            subscription_ids = (
                SubscriptionTable.query.where(SubscriptionTable.product_id.in_(product_id_sql))
                .with_entities(SubscriptionTable.subscription_id)
                .all()
            )

            for subscription_id in subscription_ids:
                yield {"subscription_id": subscription_id[0], "product_block_id": product_block_id}

        subscription_relation_dicts = list(
            chain.from_iterable(map_subscription_instance_relations(block_name) for block_name in product_names)
        )
        if subscription_relation_dicts:
            yield sql_compile(Insert(SubscriptionInstanceTable).values(subscription_relation_dicts))

    return list(
        chain.from_iterable(
            create_subscription_instance_relations(*item) for item in product_to_block_relations.items()
        )
    )


def generate_delete_product_relations_sql(delete_block_relations: Dict[str, Set[str]]) -> List[str]:
    """Generate SQL to delete product to product blocks relations.

    Args:
        - delete_block_relations: Dict with product blocks by resource type
            - key: product block name.
            - value: Set of product names to relate with.

    Returns: List of SQL strings to delete relations between product and product block.
    """

    def delete_block_relation(delete_block_name: str, product_names: Set[str]) -> str:
        product_ids_sql = get_product_ids(product_names)
        block_id_sql = get_product_block_id(delete_block_name)
        return sql_compile(
            Delete(product_product_block_association).where(
                product_product_block_association.c.product_id.in_(product_ids_sql),
                product_product_block_association.c.product_block_id.in_(block_id_sql),
            )
        )

    return [delete_block_relation(*item) for item in delete_block_relations.items()]
