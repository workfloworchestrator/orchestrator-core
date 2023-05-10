from typing import Callable

import structlog
from sqlalchemy import String, cast

from orchestrator.db import ProductBlockTable, ProductTable
from orchestrator.db.database import BaseModelMeta, SearchQuery
from orchestrator.db.filters import generic_filter

logger = structlog.get_logger(__name__)


def field_filter(table: BaseModelMeta, field: str) -> Callable:
    def _field_filter(query: SearchQuery, value: str) -> SearchQuery:
        logger.debug("Called _field_filter(...)", query=query, table=table, field=field, value=value)
        return query.filter(getattr(table, field).ilike("%" + value + "%"))

    return _field_filter


def list_filter(table: BaseModelMeta, field: str) -> Callable:
    def _list_filter(query: SearchQuery, value: str) -> SearchQuery:
        values = value.split("-")
        return query.filter(getattr(table, field).in_(values))

    return _list_filter


def id_filter(query: SearchQuery, value: str) -> SearchQuery:
    return query.filter(cast(ProductTable.product_id, String).ilike("%" + value + "%"))


def product_block_filter(query: SearchQuery, value: str) -> SearchQuery:
    """Filter ProductBlocks by '-'-separated list of Product block 'name' (column) values."""
    blocks = value.split("-")
    return query.filter(ProductTable.product_blocks.any(ProductBlockTable.name.in_(blocks)))


# TODO
# def date_filter(start: str, end: Optional[str]) -> None:
#     pass


VALID_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[SearchQuery, str], SearchQuery]] = {
    "product_id": id_filter,
    "name": field_filter(ProductTable, "name"),
    "description": field_filter(ProductTable, "description"),
    "product_type": field_filter(ProductTable, "product_type"),
    "status": list_filter(ProductTable, "status"),
    "tag": list_filter(ProductTable, "tag"),
    "product_blocks": product_block_filter,
}

filter_products = generic_filter(VALID_FILTER_FUNCTIONS_BY_COLUMN)
