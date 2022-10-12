from typing import Any, Dict, List, Set, Type, Union, get_args

from more_itertools import first
from sqlalchemy.orm import Query
from sqlalchemy.sql.expression import Delete, Insert

from orchestrator.cli.domain_gen_helpers.helpers import get_user_input, sql_compile
from orchestrator.cli.domain_gen_helpers.types import DomainModelChanges
from orchestrator.db.models import ProductBlockRelationTable, ProductBlockTable, SubscriptionInstanceTable
from orchestrator.domain.base import ProductBlockModel, get_depends_on_product_block_type_list
from orchestrator.types import is_list_type, is_union_type


def get_product_block_id(block_name: str) -> Query:
    return get_product_block_ids([block_name])


def get_product_block_ids(block_names: Union[List[str], Set[str]]) -> Query:
    return (
        ProductBlockTable.query.where(ProductBlockTable.name.in_(block_names))
        .with_entities(ProductBlockTable.product_block_id)
        .scalar_subquery()
    )


def map_create_product_blocks(product_blocks: Dict[str, Type[ProductBlockModel]]) -> Dict[str, Type[ProductBlockModel]]:
    existing_product_blocks = ProductBlockTable.query.with_entities(ProductBlockTable.name).all()
    existing_product_blocks = [block_name[0] for block_name in existing_product_blocks]
    return {
        block_name: block for block_name, block in product_blocks.items() if block_name not in existing_product_blocks
    }


def map_delete_product_blocks(product_blocks: Dict[str, Type[ProductBlockModel]]) -> List[str]:
    product_blocks_names = product_blocks.keys()
    existing_product_blocks = ProductBlockTable.query.with_entities(ProductBlockTable.name).all()
    return [name[0] for name in existing_product_blocks if name[0] not in product_blocks_names]


def get_product_block_names(block_class: Type[ProductBlockModel]) -> List[str]:
    if is_list_type(block_class):
        args = get_args(block_class)
        if not args:
            return []

        list_block_class = first(args)
        if is_union_type(list_block_class):
            return [block.name for block in get_args(list_block_class) if not isinstance(None, block)]
        return [list_block_class.name]
    if is_union_type(block_class):
        return [block.name for block in get_args(block_class) if not isinstance(None, block)]
    return [block_class.name]


def map_product_block_additional_relations(changes: DomainModelChanges) -> DomainModelChanges:
    for block_name, block_class in changes.create_product_blocks.items():
        for field_name in block_class._non_product_block_fields_.keys():
            if field_name not in changes.create_resource_type_relations:
                changes.create_resource_type_relations[field_name] = set()
            changes.create_resource_type_relations[field_name].add(block_name)

        product_blocks_in_model = block_class._get_depends_on_product_block_types()
        product_blocks_types_in_model = get_depends_on_product_block_type_list(product_blocks_in_model)
        for product_block in product_blocks_types_in_model:
            depends_on_block_names = get_product_block_names(product_block)
            for depends_on_block_name in depends_on_block_names:
                if depends_on_block_name not in changes.create_product_block_relations:
                    changes.create_product_block_relations[depends_on_block_name] = set()
                changes.create_product_block_relations[depends_on_block_name].add(block_name)
    return changes


def generate_create_product_blocks_sql(
    create_product_blocks: Dict[str, Any], inputs: Dict[str, Dict[str, str]]
) -> List[str]:
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

    return [create_product_block(name) for name in create_product_blocks.keys()]


def generate_delete_product_blocks_sql(delete_product_blocks: List[str]) -> List[str]:
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
    def create_block_relation(depends_block_name: str, block_names: Set[str]) -> str:
        depends_block_id_sql = get_product_block_id(depends_block_name)

        def create_block_relation_dict(block_name: str) -> Dict[str, Query]:
            block_id_sql = get_product_block_id(block_name)
            return {"in_use_by_id": block_id_sql, "depends_on_id": depends_block_id_sql}

        product_product_block_relation_dicts = [create_block_relation_dict(block_name) for block_name in block_names]
        return sql_compile(Insert(ProductBlockRelationTable).values(product_product_block_relation_dicts))

    return [create_block_relation(*item) for item in create_block_relations.items()]


def generate_delete_product_block_relations_sql(delete_block_relations: Dict[str, Set[str]]) -> List[str]:
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
