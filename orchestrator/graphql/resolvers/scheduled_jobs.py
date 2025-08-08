import structlog

from orchestrator.db.filters import Filter
from orchestrator.db.filters.resource_type import (
    resource_type_filter_fields,
)
from orchestrator.db.sorting import Sort
from orchestrator.db.sorting.resource_type import resource_type_sort_fields
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.schemas.scheduled_job import ScheduledJobGraphql
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils import to_graphql_result_page
from orchestrator.graphql.utils.is_query_detailed import is_querying_page_data
from orchestrator.schedules.scheduler import get_scheduler_jobs

logger = structlog.get_logger(__name__)


async def resolve_scheduled_jobs(
    info: OrchestratorInfo,
    filter_by: list[GraphqlFilter] | None = None,
    sort_by: list[GraphqlSort] | None = None,
    first: int = 10,
    after: int = 0,
) -> Connection[ScheduledJobGraphql]:
    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    jobs, total = get_scheduler_jobs(first, after, filter_by=pydantic_filter_by, sort_by=pydantic_sort_by)

    graphql_jobs = []
    if is_querying_page_data(info):
        graphql_jobs = [ScheduledJobGraphql.from_pydantic(p) for p in jobs]

    return to_graphql_result_page(
        graphql_jobs, first, after, total, resource_type_sort_fields(), resource_type_filter_fields()
    )
