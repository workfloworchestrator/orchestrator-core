from typing import Dict, List, Optional, Set, Tuple, Type, Union
from uuid import UUID

import structlog
from more_itertools import flatten
from sqlalchemy.sql.expression import Delete, Insert, Update
from sqlalchemy.sql.selectable import ScalarSelect

from orchestrator.cli.domain_gen_helpers.helpers import sql_compile
from orchestrator.cli.domain_gen_helpers.product_block_helpers import get_product_block_id, get_product_block_ids
from orchestrator.cli.domain_gen_helpers.types import DomainModelChanges
from orchestrator.cli.helpers.input_helpers import _enumerate_menu_keys, _prompt_user_menu, get_user_input
from orchestrator.cli.helpers.print_helpers import COLOR, noqa_print, print_fmt, str_fmt
from orchestrator.db.models import (
    ProductBlockTable,
    ProductTable,
    ResourceTypeTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    SubscriptionTable,
    product_block_resource_type_association,
)
from orchestrator.domain.base import ProductBlockModel

logger = structlog.get_logger(__name__)


def get_resource_type(resource_type: str) -> ScalarSelect:
    return get_resource_types([resource_type])


def get_resource_types(resource_types: Union[List[str], Set[str]]) -> ScalarSelect:
    return (
        ResourceTypeTable.query.where(ResourceTypeTable.resource_type.in_(resource_types))
        .with_entities(ResourceTypeTable.resource_type_id)
        .scalar_subquery()
    )


def map_create_resource_types(resource_type_names: Set[str], updated_resource_types: Set[str]) -> Set[str]:
    """Map resource types to create.

    Args:
        - resource_types: List of resource type names.
        - updated_resource_types: List of resource types that get renamed and don't need to be created.

    Returns: List of resource type names that can be created.
    """
    existing_resource_types = (
        ResourceTypeTable.query.where(ResourceTypeTable.resource_type.in_(resource_type_names))
        .with_entities(ResourceTypeTable.resource_type)
        .all()
    )
    existing_resource_types = {*[r_type[0] for r_type in existing_resource_types], *updated_resource_types}
    return {rt for rt in resource_type_names if rt not in existing_resource_types}


def find_resource_within_blocks(
    resource_type_names: List[str], product_blocks: Dict[str, Type[ProductBlockModel]]
) -> Set[str]:
    """Find resource types within product blocks.

    Args:
        - resource_type_names: List of resource type names.
        - product_blocks: Dict of product blocks mapped by product block name, used to check if the resource type still exists in a product block that hasn't changed.

    Returns: List of the resource_type_names that are found within product blocks.
    """
    keys = flatten([product_block._non_product_block_fields_.keys() for product_block in product_blocks.values()])
    return {field_name for field_name in keys if field_name in resource_type_names}


def map_update_resource_types(
    block_diffs: Dict[str, Dict[str, Set[str]]],
    product_blocks: Dict[str, Type[ProductBlockModel]],
    inputs: Dict[str, Dict[str, str]],
) -> Dict[str, str]:
    """Map resource types to update.

    Args:
        - block_diffs: Dict with product block differences.
            - key: product block name
            - value: Dict with differences between model and database.
                - key: difference name, 'missing_resource_types_in_model' and 'missing_resource_types_in_db' are used to check if a resource type can be renamed.
                - value: Set of resource type names.
        - product_blocks: Dict of product blocks mapped by product block name, used to check if the resource type still exists in a product block.
        - inputs: Optional Dict to specify if resource type should update.
            - key: Resource type name.
            - value: Dict with update 'y/n'.
                - key: 'update' key.
                - value: 'y/n'.

    Returns: Dict with resource types that can be updated.
        - key: old resource type name.
        - value: new resource type name.
    """

    updates = {}
    print_fmt("\nUpdate resource types", flags=[COLOR.BOLD, COLOR.UNDERLINE])
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
                        "".join(
                            [
                                "Do you wish to rename resource type ",
                                str_fmt(db_props[0], flags=[COLOR.MAGENTA]),
                                " to ",
                                str_fmt(model_props[0], flags=[COLOR.MAGENTA]),
                                "? [y/N]: ",
                            ]
                        ),
                        "N",
                    )
                )
                if should_update == "y":
                    updates[db_props[0]] = model_props[0]
    return updates


def update_resource_type_input(old_props: List[str], new_props: List[str]) -> Tuple[Optional[str], Optional[str]]:
    noqa_print("Which resource type would you want to update?")
    old_rt = _prompt_user_menu(
        [*[(p, p) for p in old_props], ("skip", None)],
        keys=[*_enumerate_menu_keys(old_props), "q"],
    )
    if not old_rt:
        return None, None

    noqa_print(f"\nWhich resource type should update {old_rt}?")
    new_rt = _prompt_user_menu(
        [*[(p, p) for p in new_props], ("skip", None)],
        keys=[*_enumerate_menu_keys(new_props), "q"],
    )
    return old_rt, new_rt if new_rt else None


def map_update_product_block_resource_types(
    block_diffs: Dict[str, Dict[str, Set[str]]],
    renamed_resource_types: Dict[str, str],
) -> Dict[str, Dict[str, str]]:
    """Map resource types to update per product block.

    Args:
        - block_diffs: Dict with product block differences.
            - key: product block name
            - value: Dict with differences between model and database.
                - key: difference name, 'missing_resource_types_in_model' and 'missing_resource_types_in_db' are used to check if a resource type can be renamed.
                - value: Set of resource type names.
        - product_blocks: Dict of product blocks mapped by product block name, used to check if the resource type still exists in a product block.
        - inputs: Optional Dict to specify if resource type should update.
            - key: Resource type name.
            - value: Dict with update 'y/n'.
                - key: 'update' key.
                - value: 'y/n'.

    Returns: Dict with resource types that can be updated.
        - key: old resource type name.
        - value: new resource type name.
    """

    updates = {}
    updated_new_rts = renamed_resource_types.values()
    print_fmt("\nUpdate block resource types", flags=[COLOR.BOLD, COLOR.UNDERLINE])
    for block_name, diff in block_diffs.items():
        db_props = list(diff.get("missing_resource_types_in_model", set()))
        model_props = list(diff.get("missing_resource_types_in_db", set()))

        old_rts = [prop for prop in db_props if prop not in renamed_resource_types]
        new_rts = [prop for prop in model_props if prop not in updated_new_rts]
        while len(old_rts) > 0 and len(new_rts) > 0:
            old_rt, new_rt = update_resource_type_input(old_rts, new_rts)
            if not old_rt:
                break
            if not new_rt:
                continue
            old_rts = [rt for rt in old_rts if rt != old_rt]
            new_rts = [rt for rt in new_rts if rt != new_rt]
            updates[block_name] = {old_rt: new_rt}
    return updates


def map_delete_resource_types(
    resource_types: Dict[str, Set[str]],
    updated_resource_types: List[str],
    product_blocks: Dict[str, Type[ProductBlockModel]],
) -> Set[str]:
    """Map resource types to delete.

    Args:
        - resource_types: List of resource type names.
        - updated_resource_types: List of resource types that get renamed and shouldn't be deleted.
        - product_blocks: Dict of product blocks mapped by product block name, used to check if the resource type still exists in a product block.

    Returns: List of resource type names that can be deleted.
    """
    resource_type_names = resource_types.keys()
    existing_resource_types = (
        ResourceTypeTable.query.where(ResourceTypeTable.resource_type.in_(resource_type_names))
        .with_entities(ResourceTypeTable.resource_type)
        .all()
    )
    existing_names = [r_type[0] for r_type in existing_resource_types if r_type[0] in resource_type_names]
    rt_with_existing_instances = {
        *find_resource_within_blocks(existing_names, product_blocks),
        *updated_resource_types,
    }
    return {name for name in existing_names if name not in rt_with_existing_instances}


def get_product_instance_count(product_id: UUID) -> int:
    return SubscriptionTable.query.where(SubscriptionTable.product_id == product_id).count()


def get_block_instance_count(product_block_id: UUID) -> int:
    return SubscriptionInstanceTable.query.where(SubscriptionInstanceTable.product_block_id == product_block_id).count()


def _has_product_existing_instances(product_name: str) -> bool:
    product: ProductTable = ProductTable.query.where(ProductTable.name == product_name).first()
    return bool(product and get_product_instance_count(product.product_id))


def _find_new_relations(block_name: str, relations: Dict[str, Set[str]]) -> Set[str]:
    return set(flatten((list(v) for k, v in relations.items() if block_name in k)))


def map_create_resource_type_instances(changes: DomainModelChanges) -> Dict[str, Set[str]]:
    """Map resource types that need a default value.

    Resource types need a default value when the related product block is used in an existing instance or will be used in an existing instance.

    Args:
        - changes: DomainModelChanges class with all changes.

    Returns: Dict with resource types that need a default value.
        - key: resource type name.
        - value: set of product block names.
    """

    def _has_existing_instances(block_name: str) -> bool:
        block: ProductBlockTable = ProductBlockTable.query.where(ProductBlockTable.name == block_name).first()
        if block and get_block_instance_count(block.product_block_id):
            return True

        related_block_names = _find_new_relations(block_name, changes.create_product_block_relations)
        if related_block_names:
            return any(_has_existing_instances(name) for name in related_block_names)

        related_product_names = _find_new_relations(block_name, changes.create_product_to_block_relations)
        return any(_has_product_existing_instances(name) for name in related_product_names)

    return {
        resource_name: {name for name in block_names if _has_existing_instances(name)}
        for resource_name, block_names in changes.create_resource_type_relations.items()
    }


def generate_create_resource_types_sql(
    resource_types: Set[str], inputs: Dict[str, Dict[str, str]], revert: bool = False
) -> List[str]:
    """Generate SQL to create resource types.

    Args:
        - resource_types: List of resource type names.
        - inputs: Optional Dict to add default value to the resource type for existing product block instances.
            - key: Resource type name.
            - value: Dict with product block by default value.
                - key: Product block name.
                - value: Default value for the resource type.

    Returns: List of SQL strings to create resource type.
    """
    print_fmt("\nCreate resource types", flags=[COLOR.BOLD, COLOR.UNDERLINE])

    def create_resource_type(resource_type: str) -> str:
        if revert:
            description = (
                ResourceTypeTable.query.where(ResourceTypeTable.resource_type == resource_type)
                .with_entities(ResourceTypeTable.description)
                .one()
            )[0]
        else:
            description = inputs.get(resource_type, {}).get("description") or get_user_input(
                f"Supply description for new resource type {str_fmt(resource_type, flags=[COLOR.MAGENTA])}: "
            )

        return sql_compile(
            Insert(ResourceTypeTable).values({"resource_type": resource_type, "description": description})
        )

    return [create_resource_type(resource_type) for resource_type in resource_types]


def generate_rename_resource_types_sql(resource_types: Dict[str, str]) -> List[str]:
    """Generate SQL to update resource types.

    Args:
        - resource_types: Dict with new resource type name by old resource type name.
            - key: old resource type name.
            - value: new resource type name.

    Returns: List of SQL strings to update resource types.
    """

    def update_resource_type(old_rt_name: str, new_rt_name: str) -> str:
        return sql_compile(
            Update(ResourceTypeTable)
            .where(ResourceTypeTable.resource_type == old_rt_name)
            .values(resource_type=new_rt_name)
        )

    return [update_resource_type(*item) for item in resource_types.items()]


def generate_delete_resource_types_sql(resource_types: Set[str]) -> List[str]:
    """Generate SQL to delete resource types.

    Args:
        - resource_types: List of resource type names.

    Returns: List of SQL strings to delete resource types.
    """
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


def generate_create_resource_type_relations_sql(resource_types: Dict[str, Set[str]]) -> List[str]:
    """Generate SQL to create resource type relations.

    Args:
        - resource_types: Dict with product blocks by resource type
            - key: Resource type name.
            - value: Set of product block names to relate with.

    Returns: List of SQL strings to create relation between product blocks and resource type.
    """

    def create_resource_type_relation(resource_type: str, block_names: Set[str]) -> str:
        resource_type_id_sql = get_resource_type(resource_type)

        def create_block_relation_dict(block_name: str) -> Dict[str, Union[str, ScalarSelect]]:
            block_id_sql = get_product_block_id(block_name)
            return {"resource_type_id": resource_type_id_sql, "product_block_id": block_id_sql}

        block_relation_dicts = [create_block_relation_dict(block_name) for block_name in block_names]
        return sql_compile(Insert(product_block_resource_type_association).values(block_relation_dicts))

    return [create_resource_type_relation(*item) for item in resource_types.items()]


def generate_create_resource_type_instance_values_sql(
    resource_types: Dict[str, Set[str]], inputs: Dict[str, Dict[str, str]]
) -> List[str]:
    """Generate SQL to create resource type instance values for existing instances.

    Args:
        - resource_types: Dict with product blocks by resource type
            - key: Resource type name.
            - value: Set of product block names to relate with.
        - inputs: Optional Dict to add default value to the resource type for existing product block instances.
            - key: Resource type name.
            - value: Dict with product block by default value.
                - key: Product block name.
                - value: Default value for the resource type.

    Returns: List of SQL strings to create subscription instance values for existing product block instances.
    """
    print_fmt("\nCreate subscription instance values", flags=[COLOR.BOLD, COLOR.UNDERLINE])

    def map_subscription_instance_relations(resource_type: str, block_name: str) -> str:
        input_value = inputs.get(resource_type, {}).get(block_name) or inputs.get(resource_type, {}).get("value")
        value = input_value or get_user_input(
            f"Supply default subscription instance value for resource type {str_fmt(resource_type, flags=[COLOR.MAGENTA])} and product block {str_fmt(block_name, flags=[COLOR.BOLD])}: "
        )

        query = """
                WITH subscription_instance_ids AS (
                    SELECT subscription_instances.subscription_instance_id
                    FROM   subscription_instances
                    WHERE  subscription_instances.product_block_id IN (
                        SELECT product_blocks.product_block_id
                        FROM   product_blocks
                        WHERE  product_blocks.name = '{0}'
                    )
                )

                INSERT INTO
                    subscription_instance_values (subscription_instance_id, resource_type_id, value)
                SELECT
                    subscription_instance_ids.subscription_instance_id,
                    resource_types.resource_type_id,
                    '{2}'
                FROM resource_types
                CROSS JOIN subscription_instance_ids
                WHERE resource_types.resource_type = '{1}'
        """
        sql_string = query.format(block_name, resource_type, value)
        logger.debug("Generated SQL", sql_string=sql_string)
        return sql_string

    sql_statements = [
        sql
        for resource_type, block_names in resource_types.items()
        for block_name in block_names
        if (sql := map_subscription_instance_relations(resource_type, block_name))
    ]
    return sql_statements


def generate_delete_resource_type_relations_sql(delete_resource_types: Dict[str, Set[str]]) -> List[str]:
    """Generate SQL to delete resource type relations and its instance values.

    Args:
        - resource_types: Dict with product blocks by resource type
            - key: Resource type name.
            - value: Set of product block names to relate with.

    Returns: List of SQL strings to delete relations between product blocks and resource type.
    """

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

    return list(flatten([delete_resource_type_relation(*item) for item in delete_resource_types.items()]))


def generate_update_resource_type_block_relations_sql(block_rt_updates: Dict[str, Dict[str, str]]) -> List[str]:
    """Generate SQL to update resource type block relations.

    Args:
        - block_rt_updates: Dict with rt updates per product block.
            - key: product block name.
            - value: Dict with new resource type name by old resource type name:
                - key: old resource type name.
                - value: new resource type name.

    Returns: List of SQL strings to update resource types.
    """

    def update_block_resource_types(block_name: str, rt_updates: Dict[str, str]) -> List[str]:
        block_id_sql = get_product_block_id(block_name)

        def update_block_relation(old_rt_name: str, new_rt_name: str) -> str:
            old_rt_id = get_resource_type(old_rt_name)
            new_rt_id = get_resource_type(new_rt_name)
            return sql_compile(
                Update(product_block_resource_type_association)
                .where(
                    product_block_resource_type_association.c.product_block_id.in_(block_id_sql),
                    product_block_resource_type_association.c.resource_type_id.in_(old_rt_id),
                )
                .values(resource_type_id=new_rt_id)
            )

        return [update_block_relation(*item) for item in rt_updates.items()]

    return list(flatten([update_block_resource_types(*item) for item in block_rt_updates.items()]))


def generate_update_resource_type_instance_values_sql(block_rt_updates: Dict[str, Dict[str, str]]) -> List[str]:
    """Generate SQL to update resource type instance values.

    Args:
        - block_rt_updates: Dict with rt updates per product block.
            - key: product block name.
            - value: Dict with new resource type name by old resource type name:
                - key: old resource type name.
                - value: new resource type name.

    Returns: List of SQL strings to update resource types.
    """

    def update_block_resource_types(block_name: str, rt_updates: Dict[str, str]) -> List[str]:
        instance_ids_sql = (
            SubscriptionInstanceTable.query.where(
                SubscriptionInstanceTable.product_block_id.in_(get_product_block_id(block_name))
            )
            .with_entities(SubscriptionInstanceTable.subscription_instance_id)
            .scalar_subquery()
        )

        def update_instance_values(old_rt_name: str, new_rt_name: str) -> str:
            old_rt_id = get_resource_type(old_rt_name)
            new_rt_id = get_resource_type(new_rt_name)
            return sql_compile(
                Update(SubscriptionInstanceValueTable)
                .where(
                    SubscriptionInstanceValueTable.subscription_instance_id.in_(instance_ids_sql),
                    SubscriptionInstanceValueTable.resource_type_id.in_(old_rt_id),
                )
                .values(resource_type_id=new_rt_id)
            )

        return [update_instance_values(*item) for item in rt_updates.items()]

    return list(flatten([update_block_resource_types(*item) for item in block_rt_updates.items()]))
