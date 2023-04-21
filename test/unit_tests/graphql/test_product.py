from dataclasses import dataclass, field
from typing import Callable

import pytest
from graphql import GraphQLError

from orchestrator.graphql import schema
from orchestrator.security import oidc_user, opa_security_graphql


@dataclass
class Context:
    errors: list[GraphQLError] = field(default_factory=list)
    get_current_user: Callable = field(default_factory=lambda: oidc_user)
    get_opa_decision: Callable = field(default_factory=lambda: opa_security_graphql)


product_test_query = """
    query TestProductQuery {
        products {
            name
            productType
            tag
            status
            productId
            description
            createdAt
        }
}
"""


@pytest.mark.asyncio
async def test_product_query(test_product_list_nested):
    result = await schema.execute(product_test_query, context_value=Context())
    assert not result.errors
    product = result.data["products"][0]
    assert product["name"] == "TestProductListNested"
    assert product["productType"] == "Test"
    assert product["tag"] == "TEST"
