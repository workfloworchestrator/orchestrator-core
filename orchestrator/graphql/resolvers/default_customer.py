from typing import Union

from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.schemas.default_customer import DefaultCustomerType
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils.to_graphql_result_page import to_graphql_result_page
from orchestrator.settings import app_settings


async def resolve_default_customer(
    info: OrchestratorInfo,
    filter_by: Union[list[GraphqlFilter], None] = None,
    sort_by: Union[list[GraphqlSort], None] = None,
    first: int = 1,
    after: int = 0,
) -> Connection[DefaultCustomerType]:
    default_customer_list = [
        DefaultCustomerType(
            fullname=app_settings.DEFAULT_CUSTOMER_FULLNAME,
            shortcode=app_settings.DEFAULT_CUSTOMER_SHORTCODE,
            identifier=app_settings.DEFAULT_CUSTOMER_IDENTIFIER,
        )
    ]
    total = len(default_customer_list)
    return to_graphql_result_page(default_customer_list, first, after, total)
