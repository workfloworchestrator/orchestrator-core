from typing import Type, TypeVar

from pydantic.utils import to_camel
from sqlalchemy import inspect

from orchestrator.db.database import BaseModel
from orchestrator.db.filters.search_filters.inferred_filter import inferred_filter, node_to_str_val

__all__ = ["inferred_filter", "default_inferred_column_clauses", "node_to_str_val"]

from orchestrator.utils.search_query import WhereCondGenerator

T = TypeVar("T", bound=Type[BaseModel])


def default_inferred_column_clauses(table: T) -> dict[str, WhereCondGenerator]:
    return {
        k: inferred_filter(column)
        for key, column in getattr(inspect(table), "columns", {}).items()
        for k in [key, to_camel(key)]
    }
