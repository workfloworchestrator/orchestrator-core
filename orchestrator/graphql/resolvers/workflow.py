import structlog
from sqlalchemy import func, select

from orchestrator.db import db
from orchestrator.db.filters import Filter
from orchestrator.db.filters.workflow import WORKFLOW_TABLE_COLUMN_CLAUSES, filter_workflows, workflow_filter_fields
from orchestrator.db.models import WorkflowTable
from orchestrator.db.range.range import apply_range_to_statement
from orchestrator.db.sorting import Sort
from orchestrator.db.sorting.workflow import sort_workflows, workflow_sort_fields
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.resolvers.helpers import rows_from_statement
from orchestrator.graphql.schemas.workflow import Workflow
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils import create_resolver_error_handler, is_querying_page_data, to_graphql_result_page
from orchestrator.graphql.utils.get_query_loaders import get_query_loaders_for_gql_fields
from orchestrator.utils.search_query import create_sqlalchemy_select

logger = structlog.get_logger(__name__)


async def resolve_workflows(
    info: OrchestratorInfo,
    filter_by: list[GraphqlFilter] | None = None,
    sort_by: list[GraphqlSort] | None = None,
    first: int = 10,
    after: int = 0,
    query: str | None = None,
) -> Connection[Workflow]:
    _error_handler = create_resolver_error_handler(info)

    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    logger.debug("resolve_workflows() called", range=[after, after + first], sort=sort_by, filter=pydantic_filter_by)

    query_loaders = get_query_loaders_for_gql_fields(WorkflowTable, info)
    select_stmt = WorkflowTable.select().options(*query_loaders)
    select_stmt = filter_workflows(select_stmt, pydantic_filter_by, _error_handler)

    if query is not None:
        stmt = create_sqlalchemy_select(
            select_stmt,
            query,
            mappings=WORKFLOW_TABLE_COLUMN_CLAUSES,
            base_table=WorkflowTable,
            join_key=WorkflowTable.workflow_id,
        )
    else:
        stmt = select_stmt

    stmt = sort_workflows(stmt, pydantic_sort_by, _error_handler)
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery()))

    stmt = apply_range_to_statement(stmt, after, after + first + 1)

    graphql_workflows = []
    if is_querying_page_data(info):
        workflows = rows_from_statement(stmt, WorkflowTable, unique=True, loaders=query_loaders)
        graphql_workflows = [Workflow.from_pydantic(p) for p in workflows]
    return to_graphql_result_page(
        graphql_workflows, first, after, total, workflow_sort_fields(), workflow_filter_fields()
    )
