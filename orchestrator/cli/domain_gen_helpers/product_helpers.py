from typing import Dict, List, Set, Type, Union

from sqlalchemy.orm import Query
from sqlalchemy.sql.expression import Delete, Insert

from orchestrator.cli.domain_gen_helpers.helpers import get_user_input, sql_compile
from orchestrator.cli.domain_gen_helpers.product_block_helpers import get_product_block_id
from orchestrator.cli.domain_gen_helpers.types import DomainModelChanges
from orchestrator.db.models import ProductTable, product_product_block_association
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
    for product_name, product_class in changes.create_products.items():
        for field_name in product_class._non_product_block_fields_.keys():
            if field_name not in changes.create_resource_types:
                changes.create_product_fixed_inputs[field_name] = set()
            changes.create_product_fixed_inputs[field_name].add(product_name)

        product_blocks_in_model = product_class._get_depends_on_product_block_types()
        product_blocks_types_in_model = get_depends_on_product_block_type_list(product_blocks_in_model)
        for product_block in product_blocks_types_in_model:
            depends_on_block_name = product_block.name
            if depends_on_block_name not in changes.create_product_to_block_relations:
                changes.create_product_to_block_relations[depends_on_block_name] = set()
            changes.create_product_to_block_relations[depends_on_block_name].add(product_name)
    return changes


def generate_create_products_sql(
    create_products: Dict[str, Type[SubscriptionModel]], inputs: Dict[str, Dict[str, str]]
) -> List[str]:
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


def generate_delete_products_sql(delete_products: List[str]) -> List[str]:
    def delete_product_block(product_name: str) -> str:
        return sql_compile(Delete(ProductTable).where(ProductTable.name == product_name))

    return [delete_product_block(product_name) for product_name in delete_products]


def generate_create_product_relations_sql(create_block_relations: Dict[str, Set[str]]) -> List[str]:
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


def generate_delete_product_relations_sql(delete_block_relations: Dict[str, Set[str]]) -> List[str]:
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
