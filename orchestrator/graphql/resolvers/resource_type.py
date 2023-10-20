from typing import Union

import structlog
from sqlalchemy import func, select

from orchestrator.db import db
from orchestrator.db.filters import Filter
from orchestrator.db.filters.resource_type import filter_resource_types, resource_type_filter_fields
from orchestrator.db.models import ResourceTypeTable
from orchestrator.db.range import apply_range_to_statement
from orchestrator.db.sorting.resource_type import resource_type_sort_fields, sort_resource_types
from orchestrator.db.sorting.sorting import Sort
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.schemas.resource_type import ResourceType
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils.create_resolver_error_handler import create_resolver_error_handler
from orchestrator.graphql.utils.to_graphql_result_page import to_graphql_result_page

logger = structlog.get_logger(__name__)


async def resolve_resource_types(
    info: OrchestratorInfo,
    filter_by: Union[list[GraphqlFilter], None] = None,
    sort_by: Union[list[GraphqlSort], None] = None,
    first: int = 10,
    after: int = 0,
) -> Connection[ResourceType]:
    _error_handler = create_resolver_error_handler(info)

    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    logger.debug(
        "resolve_resource_types() called", range=[after, after + first], sort=sort_by, filter=pydantic_filter_by
    )
    stmt = select(ResourceTypeTable)
    stmt = filter_resource_types(stmt, pydantic_filter_by, _error_handler)
    stmt = sort_resource_types(stmt, pydantic_sort_by, _error_handler)
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = apply_range_to_statement(stmt, after, after + first + 1)

    resource_types = db.session.scalars(stmt).all()
    graphql_resource_types = [ResourceType.from_pydantic(p) for p in resource_types]
    return to_graphql_result_page(
        graphql_resource_types, first, after, total, resource_type_sort_fields, resource_type_filter_fields
    )
