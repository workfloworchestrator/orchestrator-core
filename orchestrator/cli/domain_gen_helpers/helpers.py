from collections.abc import Iterable
from itertools import groupby

import structlog
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.dml import UpdateBase

from orchestrator.domain.base import ProductBlockModel

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


def map_create_product_block_relations(model_diffs: dict[str, dict[str, set[str]]]) -> dict[str, set[str]]:
    return generic_mapper("missing_product_blocks_in_db", model_diffs)


def map_delete_product_block_relations(model_diffs: dict[str, dict[str, set[str]]]) -> dict[str, set[str]]:
    return generic_mapper("missing_product_blocks_in_model", model_diffs)


def get_product_block_names(pbs: list[type[ProductBlockModel]]) -> Iterable[str]:
    return filter(None, (pb.name for pb in pbs))
