import structlog

from orchestrator.db.filters import Filter
from orchestrator.db.sorting import Sort
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.schemas.scheduled_task import ScheduledTaskGraphql
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils import create_resolver_error_handler, to_graphql_result_page
from orchestrator.graphql.utils.is_query_detailed import is_querying_page_data
from orchestrator.schedules.scheduler import get_scheduler_tasks, scheduled_task_filter_keys, scheduled_task_sort_keys

logger = structlog.get_logger(__name__)


async def resolve_scheduled_tasks(
    info: OrchestratorInfo,
    filter_by: list[GraphqlFilter] | None = None,
    sort_by: list[GraphqlSort] | None = None,
    first: int = 10,
    after: int = 0,
) -> Connection[ScheduledTaskGraphql]:
    _error_handler = create_resolver_error_handler(info)

    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    scheduled_tasks, total = get_scheduler_tasks(
        first=first, after=after, filter_by=pydantic_filter_by, sort_by=pydantic_sort_by, error_handler=_error_handler
    )

    graphql_scheduled_tasks = []
    if is_querying_page_data(info):
        graphql_scheduled_tasks = [ScheduledTaskGraphql.from_pydantic(p) for p in scheduled_tasks]

    return to_graphql_result_page(
        graphql_scheduled_tasks, first, after, total, scheduled_task_filter_keys, scheduled_task_sort_keys
    )
