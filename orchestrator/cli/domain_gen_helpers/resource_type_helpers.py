from typing import Dict, List, Set, Type, Union

from more_itertools import flatten
from sqlalchemy.orm import Query
from sqlalchemy.sql.expression import Delete, Insert, Update

from orchestrator.cli.domain_gen_helpers.helpers import get_user_input, sql_compile
from orchestrator.cli.domain_gen_helpers.product_block_helpers import get_product_block_id, get_product_block_ids
from orchestrator.db.models import (
    ResourceTypeTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    product_block_resource_type_association,
)
from orchestrator.domain.base import ProductBlockModel


def get_resource_type(resource_type: str) -> Query:
    return get_resource_types([resource_type])


def get_resource_types(resource_types: Union[List[str], Set[str]]) -> Query:
    return (
        ResourceTypeTable.query.where(ResourceTypeTable.resource_type.in_(resource_types))
        .with_entities(ResourceTypeTable.resource_type_id)
        .scalar_subquery()
    )


def map_create_resource_types(resource_types: Dict[str, Set[str]], updated_resource_types: Dict[str, str]) -> List[str]:
    resource_type_names = resource_types.keys()
    existing_resource_types = (
        ResourceTypeTable.query.where(ResourceTypeTable.resource_type.in_(resource_type_names))
        .with_entities(ResourceTypeTable.resource_type)
        .all()
    )
    existing_resource_types = [*[r_type[0] for r_type in existing_resource_types], *updated_resource_types.values()]
    return [rt for rt in resource_type_names if rt not in existing_resource_types]


def find_resource_within_blocks(
    resource_type_names: List[str], product_blocks: Dict[str, Type[ProductBlockModel]]
) -> Set[str]:
    keys = list(flatten([product_block._non_product_block_fields_.keys() for product_block in product_blocks.values()]))
    return {field_name for field_name in keys if field_name in resource_type_names}


def map_delete_resource_types(
    resource_types: Dict[str, Set[str]],
    updated_resource_type_names: List[str],
    product_blocks: Dict[str, Type[ProductBlockModel]],
) -> List[str]:
    resource_type_names = resource_types.keys()
    existing_resource_types = (
        ResourceTypeTable.query.where(ResourceTypeTable.resource_type.in_(resource_type_names))
        .with_entities(ResourceTypeTable.resource_type)
        .all()
    )
    existing_names = [r_type[0] for r_type in existing_resource_types if r_type[0] in resource_type_names]
    rt_with_existing_instances = [
        *find_resource_within_blocks(existing_names, product_blocks),
        *updated_resource_type_names,
    ]
    return [name for name in existing_names if name not in rt_with_existing_instances]


def map_update_resource_types(
    block_diffs: Dict[str, Dict[str, Set[str]]],
    product_blocks: Dict[str, Type[ProductBlockModel]],
    inputs: Dict[str, Dict[str, str]],
) -> Dict[str, str]:
    updates = {}
    print("--- UPDATE RESOURCE TYPE DECISIONS ---")  # noqa: T001, T201
    for diff in block_diffs.values():
        db_props = list(diff.get("missing_resource_types_in_model", set()))
        model_props = list(diff.get("missing_resource_types_in_db", set()))

        if (len(db_props) == 1 and len(model_props) == 1) and db_props[0] not in updates:
            existing_in_blocks = find_resource_within_blocks(db_props, product_blocks)
            if not existing_in_blocks:
                prefilled_val = inputs.get(db_props[0], {}).get("update")
                should_update = (
                    prefilled_val
                    if prefilled_val
                    else get_user_input(
                        f"Change resource type {db_props} to {model_props} (y/N): ",
                        "n",
                    )
                )
                if should_update == "y":
                    updates[db_props[0]] = model_props[0]

    for name, diff in block_diffs.items():
        db_props = list(diff.get("missing_resource_types_in_model", set()))
        model_props = list(diff.get("missing_resource_types_in_db", set()))

        for key, value in updates.items():
            if key in db_props and value in model_props:
                db_props.remove(key)
                model_props.remove(value)

        block_diffs[name]["missing_resource_types_in_model"] = set(db_props)
        block_diffs[name]["missing_resource_types_in_db"] = set(model_props)
    return updates


def generate_create_resource_types_sql(
    resource_types: List[str], inputs: Dict[str, Dict[str, str]], revert: bool = False
) -> List[str]:
    def create_resource_type(resource_type: str) -> str:
        if revert:
            description = (
                ResourceTypeTable.query.where(ResourceTypeTable.resource_type == resource_type)
                .with_entities(ResourceTypeTable.description)
                .one()
            )[0]
        else:
            print(f"--- RESOURCE TYPE ['{resource_type}'] ---")  # noqa: T001, T201
            description = inputs.get(resource_type, {}).get("description") or get_user_input(
                "Resource type description: "
            )

        return sql_compile(
            Insert(ResourceTypeTable).values({"resource_type": resource_type, "description": description})
        )

    return [create_resource_type(resource_type) for resource_type in resource_types]


def generate_update_resource_types_sql(resource_types: Dict[str, str]) -> List[str]:
    def update_resource_type(old_rt_name: str, new_rt_name: str) -> str:
        return sql_compile(
            Update(ResourceTypeTable)
            .where(ResourceTypeTable.resource_type == old_rt_name)
            .values(resource_type=new_rt_name)
        )

    return [update_resource_type(*item) for item in resource_types.items()]


def generate_delete_resource_types_sql(resource_types: List[str]) -> List[str]:
    if not resource_types:
        return []
    return [
        sql_compile(
            Delete(SubscriptionInstanceValueTable).where(
                SubscriptionInstanceValueTable.resource_type_id.in_(get_resource_types(resource_types))
            )
        ),
        sql_compile(Delete(ResourceTypeTable).where(ResourceTypeTable.resource_type.in_(resource_types))),
    ]


def generate_create_resource_type_relations_sql(
    resource_types: Dict[str, Set[str]], inputs: Dict[str, Dict[str, str]]
) -> List[str]:
    def create_resource_type_relation(resource_type: str, block_names: Set[str]) -> List[str]:
        resource_type_id_sql = get_resource_type(resource_type)

        def create_block_relation_dict(block_name: str) -> Dict[str, Union[str, Query]]:
            block_id_sql = get_product_block_id(block_name)
            return {"resource_type_id": resource_type_id_sql, "product_block_id": block_id_sql}

        def create_subscription_block_relations(block_name: str) -> List[Dict[str, Union[str, Query]]]:
            input_value = inputs.get(resource_type, {}).get(block_name) or inputs.get(resource_type, {}).get("value")
            value = input_value or get_user_input(
                f"Resource type ['{resource_type}'] default value for block ['{block_name}']: "
            )

            block_id_sql = get_product_block_id(block_name)
            subscription_instance_ids = (
                SubscriptionInstanceTable.query.where(SubscriptionInstanceTable.product_block_id.in_(block_id_sql))
                .with_entities(SubscriptionInstanceTable.subscription_instance_id)
                .all()
            )
            return [
                {"resource_type_id": resource_type_id_sql, "subscription_instance_id": instance_id[0], "value": value}
                for instance_id in subscription_instance_ids
            ]

        block_relation_dicts = [create_block_relation_dict(block_name) for block_name in block_names]
        subscription_relation_dicts = list(
            flatten([create_subscription_block_relations(block_name) for block_name in block_names])
        )
        block_relations = sql_compile(Insert(product_block_resource_type_association).values(block_relation_dicts))
        if subscription_relation_dicts:
            subscription_block_relations = sql_compile(
                Insert(SubscriptionInstanceValueTable).values(subscription_relation_dicts)
            )
            return [block_relations, subscription_block_relations]
        return [block_relations]

    return flatten([create_resource_type_relation(*item) for item in resource_types.items()])


def generate_delete_resource_type_relations_sql(delete_resource_types: Dict[str, Set[str]]) -> List[str]:
    def delete_resource_type_relation(resource_type: str, block_names: Set[str]) -> List[str]:
        block_ids_sql = get_product_block_ids(block_names)
        resource_type_id_sql = get_resource_type(resource_type)
        subscription_instance_id_sql = (
            SubscriptionInstanceTable.query.where(SubscriptionInstanceTable.subscription_instance_id.in_(block_ids_sql))
            .with_entities(SubscriptionInstanceTable.subscription_instance_id)
            .scalar_subquery()
        )
        return [
            sql_compile(
                Delete(product_block_resource_type_association).where(
                    product_block_resource_type_association.c.product_block_id.in_(block_ids_sql),
                    product_block_resource_type_association.c.resource_type_id == resource_type_id_sql,
                )
            ),
            sql_compile(
                Delete(SubscriptionInstanceValueTable).where(
                    SubscriptionInstanceValueTable.subscription_instance_id.in_(subscription_instance_id_sql),
                    product_block_resource_type_association.c.resource_type_id == resource_type_id_sql,
                )
            ),
        ]

    return flatten([delete_resource_type_relation(*item) for item in delete_resource_types.items()])
