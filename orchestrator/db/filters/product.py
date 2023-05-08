from typing import Callable

import structlog
from sqlalchemy import String, cast

from orchestrator.db import ProductBlockTable, ProductTable, db
from orchestrator.db.database import BaseModelMeta, SearchQuery
from orchestrator.db.filters import generic_filter

logger = structlog.get_logger(__name__)


def generic_field_filter(table: BaseModelMeta, field: str) -> Callable:
    def _generic_field_filter(query: SearchQuery, value: str) -> SearchQuery:
        logger.debug("Called generic_field_filter(...)", query=query, table=table, field=field, value=value)
        return query.filter(getattr(table, field).ilike("%" + value + "%"))

    return _generic_field_filter


def generic_list_filter(table: BaseModelMeta, field: str) -> Callable:
    def _generic_list_filter(query: SearchQuery, value: str) -> SearchQuery:
        values = value.split("-")
        return query.filter(getattr(table, field).in_(values))

    return _generic_list_filter


def id_filter(query: SearchQuery, value: str) -> SearchQuery:
    return query.filter(cast(ProductTable.product_id, String).ilike("%" + value + "%"))


# def name_filter(query: SearchQuery, value: str) -> SearchQuery:
#     return query.filter(ProductTable.name.ilike("%" + value + "%"))


def status_filter(query: SearchQuery, value: str) -> SearchQuery:
    statuses = value.split("-")
    return query.filter(ProductTable.last_status.in_(statuses))


def product_block_filter(query: SearchQuery, value: str) -> SearchQuery:
    blocks = value.split("-")
    product_blocks = db.session.query(ProductBlockTable).filter(ProductBlockTable.name.in_(blocks)).subquery()
    return query.filter(product_blocks.c.product_id == ProductTable.product_id)


# TODO
# def date_filter(start: str, end: Optional[str]) -> None:
#     pass


VALID_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[SearchQuery, str], SearchQuery]] = {
    "product_id": id_filter,
    "name": generic_field_filter(ProductTable, "name"),
    "description": generic_field_filter(ProductTable, "description"),
    "product_type": generic_field_filter(ProductTable, "product_type"),
    "status": generic_list_filter(ProductTable, "status"),
    "tag": generic_list_filter(ProductTable, "tag"),
    "product_blocks": product_block_filter,
}

filter_products = generic_filter(VALID_FILTER_FUNCTIONS_BY_COLUMN)
