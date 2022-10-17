#!/usr/bin/env python3

"""Create migration for models based on diff_product_in_database.

$ PYTHONPATH=. python bin/list_workflows

"""
from typing import Dict, List, Set, Tuple, Type, Union
from uuid import UUID

import structlog

from orchestrator.cli.domain_gen_helpers.fixed_input_helpers import (
    generate_create_fixed_inputs_sql,
    generate_delete_fixed_inputs_sql,
    generate_update_fixed_inputs_sql,
    map_update_fixed_inputs,
)
from orchestrator.cli.domain_gen_helpers.helpers import (
    map_create_fixed_inputs,
    map_create_product_block_relations,
    map_create_resource_type_relations,
    map_delete_fixed_inputs,
    map_delete_product_block_relations,
    map_delete_resource_type_relations,
)
from orchestrator.cli.domain_gen_helpers.product_block_helpers import (
    generate_create_product_block_instance_relations_sql,
    generate_create_product_block_relations_sql,
    generate_create_product_blocks_sql,
    generate_delete_product_block_relations_sql,
    generate_delete_product_blocks_sql,
    map_create_product_blocks,
    map_delete_product_blocks,
    map_product_block_additional_relations,
)
from orchestrator.cli.domain_gen_helpers.product_helpers import (
    generate_create_product_instance_relations_sql,
    generate_create_product_relations_sql,
    generate_create_products_sql,
    generate_delete_product_relations_sql,
    generate_delete_products_sql,
    map_product_additional_relations,
)
from orchestrator.cli.domain_gen_helpers.resource_type_helpers import (
    generate_create_resource_type_instance_relations_sql,
    generate_create_resource_type_relations_sql,
    generate_create_resource_types_sql,
    generate_delete_resource_type_relations_sql,
    generate_delete_resource_types_sql,
    generate_update_resource_types_sql,
    map_create_resource_types,
    map_delete_resource_types,
    map_update_resource_types,
)
from orchestrator.cli.domain_gen_helpers.types import DomainModelChanges
from orchestrator.db import init_database
from orchestrator.db.models import ProductTable
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import ProductBlockModel, SubscriptionModel, get_depends_on_product_block_type_list
from orchestrator.settings import app_settings

logger = structlog.get_logger(__name__)


def should_skip(product_name: str) -> bool:
    return any(name in product_name.lower() for name in app_settings.SKIP_MODEL_FOR_MIGRATION_DB_DIFF)


def map_product_blocks_in_class(
    model_class: Union[Type[SubscriptionModel], Type[ProductBlockModel]],
    product_blocks: Dict[str, Type[ProductBlockModel]],
) -> Dict[str, Type[ProductBlockModel]]:
    """Create mapping of all existing product block models related to a model.

    Args:
        - model_class: a product class (SubscriptionModel) or product block class (ProductBlockModel).

    Returns a Dict with product block models by product block name.
    """
    product_blocks_types_in_model = get_depends_on_product_block_type_list(
        model_class._get_depends_on_product_block_types()
    )

    new_blocks = {
        block.name: block for block in product_blocks_types_in_model if block.name not in product_blocks.keys()
    }
    product_blocks = {**product_blocks, **new_blocks}

    blocks_map = {
        name: block_cls
        for block in new_blocks.values()
        for name, block_cls in map_product_blocks_in_class(block, product_blocks).items()
        if block_cls.name not in product_blocks.keys()
    }
    return {**product_blocks, **blocks_map}


def map_product_blocks(product_classes: List[Type[SubscriptionModel]]) -> Dict[str, Type[ProductBlockModel]]:
    """Create mapping of all existing product block models related to products.

    Args:
        - product_classes: List of product classes.

    Returns a Dict with product block models by product block name.
    """

    product_blocks: Dict[str, Type[ProductBlockModel]] = {}
    for product_class in product_classes:
        product_blocks = {**product_blocks, **map_product_blocks_in_class(product_class, product_blocks)}
    return product_blocks


def map_differences_unique(
    registered_products: Dict[str, Type[SubscriptionModel]], existing_products: List[Tuple[str, UUID]]
) -> Dict[str, Dict[str, Dict[str, Set[str]]]]:
    """Create a unique map for products and product block differences from the database.

    Args:
        - registered_products: Dict with product models by product name.
        - existing_products: List with tuples of product name and its uuid that exist in the database.

    Returns a dict with product and product block differences from the database without duplicates.
    """
    model_diffs: Dict[str, Dict[str, Dict[str, Set[str]]]] = {"products": {}, "blocks": {}}

    for product_name, product_id in existing_products:
        if should_skip(product_name) or product_name not in registered_products.keys():
            continue

        product_class = registered_products[product_name]
        if diff := product_class.diff_product_in_database(product_id):
            model_diffs["products"][product_name] = {**diff[product_name], "missing_in_depends_on_blocks": []}  # type: ignore

            if missing_in_depends_on_blocks := diff[product_name].get("missing_in_depends_on_blocks"):
                model_diff_keys = model_diffs["blocks"].keys()
                # since missing_in_depends_on_blocks is always a dict the type is ignored.
                new_model_diffs = {
                    name: diff for name, diff in missing_in_depends_on_blocks.items() if name not in model_diff_keys  # type: ignore
                }
                model_diffs["blocks"] = {**model_diffs["blocks"], **new_model_diffs}  # type: ignore
    return model_diffs


def map_changes(
    model_diffs: Dict[str, Dict[str, Dict[str, Set[str]]]],
    products: Dict[str, Type[SubscriptionModel]],
    product_blocks: Dict[str, Type[ProductBlockModel]],
    db_product_names: List[str],
    inputs: Dict[str, Dict[str, str]],
) -> DomainModelChanges:
    """Map changes that need to be made to fix differences between models and database.

    Args:
        - model_diffs: Dict with product and product block differences.
            - products: Dict with product differences.
            - blocks: Dict with product block differences.
        - products: Dict with product model by product name.
        - product_blocks: Dict with product block model by product name.
        - db_product_names: Product names out of the database.
        - inputs: Optional Dict with prefilled values.

    Returns: Mapped changes.
    """
    create_products = {name: model for name, model in products.items() if name not in db_product_names}
    delete_products = [name for name in db_product_names if name not in SUBSCRIPTION_MODEL_REGISTRY.keys()]

    # updates need to go before create or deletes.
    update_product_fixed_inputs = map_update_fixed_inputs(model_diffs["products"])
    update_resource_types = map_update_resource_types(model_diffs["blocks"], product_blocks, inputs)

    create_resource_type_relations = map_create_resource_type_relations(model_diffs["blocks"])
    delete_resource_type_relations = map_delete_resource_type_relations(model_diffs["blocks"])

    changes = DomainModelChanges(
        create_products=create_products,
        delete_products=delete_products,
        create_product_fixed_inputs=map_create_fixed_inputs(model_diffs["products"]),
        update_product_fixed_inputs=update_product_fixed_inputs,
        delete_product_fixed_inputs=map_delete_fixed_inputs(model_diffs["products"]),
        create_product_to_block_relations=map_create_product_block_relations(model_diffs["products"]),
        delete_product_to_block_relations=map_delete_product_block_relations(model_diffs["products"]),
        update_resource_types=update_resource_types,
        delete_resource_types=map_delete_resource_types(
            delete_resource_type_relations, list(update_resource_types.keys()), product_blocks
        ),
        create_resource_type_relations=create_resource_type_relations,
        delete_resource_type_relations=delete_resource_type_relations,
        create_product_blocks=map_create_product_blocks(product_blocks),
        delete_product_blocks=map_delete_product_blocks(product_blocks),
        create_product_block_relations=map_create_product_block_relations(model_diffs["blocks"]),
        delete_product_block_relations=map_delete_product_block_relations(model_diffs["blocks"]),
    )

    changes = map_product_additional_relations(changes)
    changes = map_product_block_additional_relations(changes)
    changes.create_resource_types = map_create_resource_types(
        changes.create_resource_type_relations, update_resource_types
    )
    return changes


def generate_upgrade_sql(changes: DomainModelChanges, inputs: Dict[str, Dict[str, str]]) -> List[str]:
    """Generate upgrade SQL with mapped changes.

    Args:
        - changes: Mapping of model changes.
        - inputs: Optional Dict with prefilled values.

    Returns: List of SQL strings to upgrade the database.
    """
    return [
        *generate_update_fixed_inputs_sql(changes.update_product_fixed_inputs),
        *generate_update_resource_types_sql(changes.update_resource_types),
        *generate_delete_resource_type_relations_sql(changes.delete_resource_type_relations),
        *generate_delete_product_block_relations_sql(changes.delete_product_block_relations),
        *generate_delete_product_relations_sql(changes.delete_product_to_block_relations),
        *generate_delete_resource_types_sql(changes.delete_resource_types),
        *generate_delete_product_blocks_sql(changes.delete_product_blocks),
        *generate_delete_fixed_inputs_sql(changes.delete_product_fixed_inputs),
        *generate_delete_products_sql(changes.delete_products),
        *generate_create_products_sql(changes.create_products, inputs),
        *generate_create_fixed_inputs_sql(changes.create_product_fixed_inputs, inputs),
        *generate_create_product_blocks_sql(changes.create_product_blocks, inputs),
        *generate_create_resource_types_sql(changes.create_resource_types, inputs),
        *generate_create_product_relations_sql(changes.create_product_to_block_relations),
        *generate_create_product_block_relations_sql(changes.create_product_block_relations),
        *generate_create_resource_type_relations_sql(changes.create_resource_type_relations),
        *generate_create_product_instance_relations_sql(changes.create_product_to_block_relations),
        *generate_create_product_block_instance_relations_sql(changes.create_product_block_relations),
        *generate_create_resource_type_instance_relations_sql(changes.create_resource_type_relations, inputs),
    ]


def generate_downgrade_sql(changes: DomainModelChanges) -> List[str]:
    """Generate downgrade SQL with mapped changes.

    Does not revert deleted subscription instances and subscription instance values!

    Args:
        - changes: Mapping of model changes.

    Returns: List of SQL strings to downgrade the database back before upgrade SQL.
    """
    sql_revert_create_fixed_inputs = generate_delete_fixed_inputs_sql(changes.create_product_fixed_inputs)

    update_revert_map = {
        name: {new: old for old, new in updates.items()}
        for name, updates in changes.update_product_fixed_inputs.items()
    }
    sql_revert_update_fixed_inputs = generate_update_fixed_inputs_sql(update_revert_map)
    sql_revert_delete_fixed_inputs = generate_create_fixed_inputs_sql(
        changes.delete_product_fixed_inputs, {}, revert=True
    )

    sql_revert_create_resource_type_relations = generate_delete_resource_type_relations_sql(
        changes.create_resource_type_relations
    )
    sql_revert_create_resource_types = generate_delete_resource_types_sql(changes.create_resource_types)
    sql_revert_update_resource_types = generate_update_resource_types_sql(
        {new: old for old, new in changes.update_resource_types.items()}
    )

    sql_revert_create_product_product_block_relations = generate_delete_product_relations_sql(
        changes.create_product_to_block_relations,
    )
    sql_revert_create_product_block_depends_blocks = generate_delete_product_block_relations_sql(
        changes.create_product_block_relations
    )

    sql_revert_create_product_blocks = generate_delete_product_blocks_sql(list(changes.create_product_blocks.keys()))
    sql_revert_create_products = generate_delete_products_sql(list(changes.create_products.keys()))

    return [
        *sql_revert_create_resource_type_relations,
        *sql_revert_create_resource_types,
        *sql_revert_create_product_product_block_relations,
        *sql_revert_create_product_block_depends_blocks,
        *sql_revert_create_fixed_inputs,
        *sql_revert_create_product_blocks,
        *sql_revert_create_products,
        *sql_revert_delete_fixed_inputs,
        *sql_revert_update_resource_types,
        *sql_revert_update_fixed_inputs,
    ]


def create_domain_models_migration_sql(inputs: Dict[str, Dict[str, str]]) -> Tuple[List[str], List[str]]:
    """Create tuple with list for upgrade and downgrade sql statements based on SubscriptionModel.diff_product_in_database.

    You will be prompted with inputs for new models and resource type updates.

    Args:
        - inputs: dict with pre-defined input values

    Returns tuple:
        - list of upgrade sql statements in string format.
        - list of downgrade sql statements in string format.
    """

    if not app_settings.TESTING:
        init_database(app_settings)

    existing_products: List[Tuple[str, UUID]] = list(
        ProductTable.query.with_entities(ProductTable.name, ProductTable.product_id)
    )
    db_product_names: List[str] = [product_name for product_name, _ in existing_products]

    products = SUBSCRIPTION_MODEL_REGISTRY
    product_blocks = map_product_blocks(list(SUBSCRIPTION_MODEL_REGISTRY.values()))
    model_diffs = map_differences_unique(products, existing_products)

    changes = map_changes(model_diffs, products, product_blocks, db_product_names, inputs)

    logger.debug("create_products", create_products=changes.create_products)
    logger.debug("delete_products", delete_products=changes.delete_products)
    logger.debug("create_product_fixed_inputs", create_product_fixed_inputs=changes.create_product_fixed_inputs)
    logger.debug("update_product_fixed_inputs", update_product_fixed_inputs=changes.update_product_fixed_inputs)
    logger.debug("delete_product_fixed_inputs", delete_product_fixed_inputs=changes.delete_product_fixed_inputs)
    logger.debug(
        "create_product_to_block_relations", create_product_to_block_relations=changes.create_product_to_block_relations
    )
    logger.debug(
        "delete_product_to_block_relations", delete_product_to_block_relations=changes.delete_product_to_block_relations
    )
    logger.debug("create_resource_types", create_resource_types=changes.create_resource_types)
    logger.debug("update_resource_types", update_resource_types=changes.update_resource_types)
    logger.debug("delete_resource_types", delete_resource_types=changes.delete_resource_types)
    logger.debug(
        "create_resource_type_relations", create_resource_type_relations=changes.create_resource_type_relations
    )
    logger.debug(
        "delete_resource_type_relations", delete_resource_type_relations=changes.delete_resource_type_relations
    )
    logger.debug("create_product_blocks", create_blocks=changes.create_product_blocks)
    logger.debug("delete_product_blocks", delete_blocks=changes.delete_product_blocks)
    logger.debug(
        "create_product_block_relations", create_product_block_relations=changes.create_product_block_relations
    )
    logger.debug(
        "delete_product_block_relations", delete_product_block_relations=changes.delete_product_block_relations
    )

    sql_upgrade_stmts = generate_upgrade_sql(changes, inputs)
    sql_downgrade_stmts = generate_downgrade_sql(changes)

    return sql_upgrade_stmts, sql_downgrade_stmts
