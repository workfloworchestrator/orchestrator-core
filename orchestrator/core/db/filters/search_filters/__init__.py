from sqlalchemy import inspect

from orchestrator.core.db.database import BaseModel
from orchestrator.core.db.filters.search_filters.inferred_filter import filter_exact, inferred_filter, node_to_str_val

__all__ = ["inferred_filter", "default_inferred_column_clauses", "node_to_str_val", "filter_exact"]

from orchestrator.core.utils.search_query import WhereCondGenerator


def default_inferred_column_clauses(table: type[BaseModel]) -> dict[str, WhereCondGenerator]:
    return {key: inferred_filter(column) for key, column in getattr(inspect(table), "columns", {}).items()}
