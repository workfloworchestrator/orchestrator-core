from collections.abc import Iterable
from itertools import groupby

import structlog
import typer
from more_itertools import first
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.dml import UpdateBase

from orchestrator.cli.domain_gen_helpers.types import BlockRelationDict
from orchestrator.cli.helpers.input_helpers import _prompt_user_menu
from orchestrator.cli.helpers.print_helpers import noqa_print
from orchestrator.domain.base import ProductBlockModel, SubscriptionModel

logger = structlog.get_logger(__name__)


def sql_compile(sql: UpdateBase) -> str:
    sql_string = str(sql.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))  # type: ignore[no-untyped-call]
    sql_string = sql_string.replace("\n", "")
    logger.debug("generated SQL", sql_string=sql_string)
    return sql_string


def generic_mapper(prop_name: str, model_diffs: dict[str, dict[str, set[str]]]) -> dict[str, set[str]]:
    model_by_resource = [
        (prop_name_value, model_name)
        for model_name, diff in model_diffs.items()
        for prop_name_value in diff.get(prop_name, [])
    ]
    grouped = groupby(model_by_resource, lambda x: x[0])
    return {k: {val[1] for val in v} for k, v in grouped}


def map_create_fixed_inputs(model_diffs: dict[str, dict[str, set[str]]]) -> dict[str, set[str]]:
    return generic_mapper("missing_fixed_inputs_in_db", model_diffs)


def map_delete_fixed_inputs(model_diffs: dict[str, dict[str, set[str]]]) -> dict[str, set[str]]:
    return generic_mapper("missing_fixed_inputs_in_model", model_diffs)


def map_create_resource_type_relations(model_diffs: dict[str, dict[str, set[str]]]) -> dict[str, set[str]]:
    return generic_mapper("missing_resource_types_in_db", model_diffs)


def map_delete_resource_type_relations(model_diffs: dict[str, dict[str, set[str]]]) -> dict[str, set[str]]:
    return generic_mapper("missing_resource_types_in_model", model_diffs)


def map_create_product_to_product_block_relations(model_diffs: dict[str, dict[str, set[str]]]) -> dict[str, set[str]]:
    return generic_mapper("missing_product_blocks_in_db", model_diffs)


def format_block_relation_to_dict(
    model_name: str,
    block_to_find_in_props: str,
    models: dict[str, type[SubscriptionModel]] | dict[str, type[ProductBlockModel]],
    confirm_warnings: bool,
) -> BlockRelationDict:
    model = models[model_name]
    block_props = model._get_depends_on_product_block_types()
    props = {k for k, v in block_props.items() if v.name == block_to_find_in_props}  # type: ignore

    if len(props) > 1 and not confirm_warnings:
        noqa_print("WARNING: Relating a Product Block multiple times is not supported by this migrator!")
        noqa_print(
            "You will need to create your own migration to create a Product Block Instance for each attribute that is related"
        )
        noqa_print(f"Product Block '{block_to_find_in_props}' has been related multiple times to '{model_name}'")
        noqa_print(f"Attributes the block ('{block_to_find_in_props}') has been related with: {', '.join(props)}")
        noqa_print(f"The relation will only be added to the first attribute ('{first(props)}') want to continue?")

        if _prompt_user_menu([("yes", "yes"), ("no", "no")]) == "no":
            typer.echo("Aborted.")
            raise typer.Exit(code=1)

    return BlockRelationDict(name=model_name, attribute_name=first(props))


def map_create_product_block_relations(
    model_diffs: dict[str, dict[str, set[str]]],
    models: dict[str, type[SubscriptionModel]] | dict[str, type[ProductBlockModel]],
    confirm_warnings: bool,
) -> dict[str, list[BlockRelationDict]]:
    data = generic_mapper("missing_product_blocks_in_db", model_diffs)
    return {
        k: [format_block_relation_to_dict(b, k, models, confirm_warnings) for b in blocks] for k, blocks in data.items()
    }


def map_delete_product_block_relations(model_diffs: dict[str, dict[str, set[str]]]) -> dict[str, set[str]]:
    return generic_mapper("missing_product_blocks_in_model", model_diffs)


def get_product_block_names(pbs: list[type[ProductBlockModel]]) -> Iterable[str]:
    return filter(None, (pb.name for pb in pbs))
