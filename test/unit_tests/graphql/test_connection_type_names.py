# Copyright 2019-2026 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
import strawberry
from graphql import parse, validate

from orchestrator.core.graphql.schema import Query
from orchestrator.core.graphql.types import SCALAR_OVERRIDES


@pytest.fixture(scope="module")
def schema():
    return strawberry.federation.Schema(query=Query, scalar_overrides=SCALAR_OVERRIDES)


# Clients hold fragments on these type names; renaming one rejects their queries at validation.
@pytest.mark.parametrize(
    ("field", "type_name"),
    [
        ("processes", "ProcessTypeConnection"),
        ("products", "ProductTypeConnection"),
        ("productBlocks", "ProductBlockConnection"),
        ("resourceTypes", "ResourceTypeConnection"),
        ("workflows", "WorkflowConnection"),
        ("subscriptions", "SubscriptionInterfaceConnection"),
    ],
)
def test_fragment_on_existing_connection_type_validates(schema, field, type_name):
    query = f"""
    query {{ {field} {{ ...connection }} }}
    fragment connection on {type_name} {{ pageInfo {{ totalItems }} searchEdges {{ score }} nextPageCursor }}
    """

    assert validate(schema._schema, parse(query)) == []
