from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.schemas.customer import CustomerType
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils.to_graphql_result_page import to_graphql_result_page
from orchestrator.settings import app_settings


async def resolve_customer(
    info: OrchestratorInfo,
    filter_by: list[GraphqlFilter] | None = None,
    sort_by: list[GraphqlSort] | None = None,
    first: int = 1,
    after: int = 0,
) -> Connection[CustomerType]:
    default_customer_list = [
        CustomerType(
            customer_id=app_settings.DEFAULT_CUSTOMER_IDENTIFIER,
            fullname=app_settings.DEFAULT_CUSTOMER_FULLNAME,
            shortcode=app_settings.DEFAULT_CUSTOMER_SHORTCODE,
        )
    ]
    total = len(default_customer_list)
    return to_graphql_result_page(default_customer_list, first, after, total)
