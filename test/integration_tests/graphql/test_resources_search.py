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
"""Tests for the `search` argument of the processes, products, productBlocks, resourceTypes and workflows queries.

The search machinery is shared with `subscriptions` and covered in depth by test_subscriptions_search.py; these tests
pin that every resource is wired to its own entity type and loads its own rows. Search runs filter-only (structured
retriever) against hand-written index rows, so no embeddings are needed.
"""

import json
from dataclasses import dataclass
from http import HTTPStatus
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy_utils import Ltree

from orchestrator.core.db import ProcessTable, ProductBlockTable, ProductTable, ResourceTypeTable, WorkflowTable, db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import EntityType, FieldType
from test.integration_tests.config import GRAPHQL_ENDPOINT, GRAPHQL_HEADERS


@dataclass(frozen=True)
class Resource:
    field: str
    entity_type: EntityType
    table: type
    id_field: str

    @property
    def id_column(self):
        return getattr(self.table, self.id_field)

    @property
    def gql_id(self) -> str:
        head, *tail = self.id_field.split("_")
        return head + "".join(part.title() for part in tail)

    @property
    def path(self) -> str:
        return f"{self.entity_type.value.lower()}.marker"


PROCESSES = Resource("processes", EntityType.PROCESS, ProcessTable, "process_id")
RESOURCES = [
    pytest.param(PROCESSES, id="processes"),
    pytest.param(Resource("products", EntityType.PRODUCT, ProductTable, "product_id"), id="products"),
    pytest.param(
        Resource("productBlocks", EntityType.PRODUCT_BLOCK, ProductBlockTable, "product_block_id"), id="product-blocks"
    ),
    pytest.param(
        Resource("resourceTypes", EntityType.RESOURCE_TYPE, ResourceTypeTable, "resource_type_id"), id="resource-types"
    ),
    pytest.param(Resource("workflows", EntityType.WORKFLOW, WorkflowTable, "workflow_id"), id="workflows"),
]


def _query(resource: Resource) -> str:
    return f"""
query ResourceSearch($search: ResourceSearchInput, $first: Int) {{
    {resource.field}(search: $search, first: $first) {{
        page {{
            {resource.gql_id}
        }}
        searchEdges {{
            node {{
                {resource.gql_id}
            }}
            score
        }}
        searchMetadata {{
            searchType
        }}
        nextPageCursor
        pageInfo {{
            hasNextPage
            hasPreviousPage
            totalItems
        }}
    }}
}}
"""


def _index_row(entity_type: EntityType, entity_id: UUID, path: str, value: str) -> AiSearchIndex:
    return AiSearchIndex(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_title=f"title {entity_id}",
        path=Ltree(path),
        value=value,
        value_type=FieldType.STRING,
        content_hash=uuid4().hex,
    )


def _marker_filter(resource: Resource) -> dict:
    return {
        "op": "AND",
        "filters": [{"path": resource.path, "condition": {"op": "EQ", "value": "hit"}, "valueKind": "STRING"}],
    }


@pytest.fixture
def seeded_rows(
    mocked_processes, generic_product_1, generic_product_2, generic_product_3, generic_product_block_3
) -> None:
    """Rows of every resource; the fixtures above guarantee at least three of each."""


@pytest.fixture(params=RESOURCES)
def resource(request) -> Resource:
    return request.param


@pytest.fixture
def indexed_ids(seeded_rows, resource) -> list[UUID]:
    """Index three rows of the resource as hits and one as a miss, which the marker filter excludes."""
    *hits, miss = db.session.scalars(select(resource.id_column).order_by(resource.id_column).limit(4)).all()
    db.session.add_all(
        [_index_row(resource.entity_type, entity_id, resource.path, "hit") for entity_id in hits]
        + [_index_row(resource.entity_type, miss, resource.path, "miss")]
    )
    db.session.commit()
    return hits


def _post(test_client_graphql, resource: Resource, **variables) -> dict:
    data = json.dumps({"query": _query(resource), "variables": variables})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    return response.json()


def test_search_returns_hits_of_resource(test_client_graphql, indexed_ids, resource):
    result = _post(test_client_graphql, resource, search={"filters": _marker_filter(resource), "limit": 10})

    assert "errors" not in result
    connection = result["data"][resource.field]
    edge_ids = [edge["node"][resource.gql_id] for edge in connection["searchEdges"]]
    assert sorted(edge_ids) == sorted(str(entity_id) for entity_id in indexed_ids)
    assert connection["page"] == []
    assert connection["searchMetadata"]["searchType"] == "structured"
    assert connection["pageInfo"] == {"hasNextPage": False, "hasPreviousPage": False, "totalItems": 3}


def test_search_cursor_pages_through_hits(test_client_graphql, indexed_ids, resource):
    first = _post(test_client_graphql, resource, search={"filters": _marker_filter(resource), "limit": 2})
    first_page = first["data"][resource.field]
    second = _post(test_client_graphql, resource, search={"cursor": first_page["nextPageCursor"]})

    assert "errors" not in second
    second_page = second["data"][resource.field]
    seen = [edge["node"][resource.gql_id] for edge in first_page["searchEdges"] + second_page["searchEdges"]]
    assert sorted(seen) == sorted(str(entity_id) for entity_id in indexed_ids)
    assert second_page["pageInfo"]["hasPreviousPage"] is True
    assert second_page["nextPageCursor"] is None


def test_search_combined_with_legacy_argument_is_rejected(test_client_graphql, resource):
    result = _post(test_client_graphql, resource, search={"filters": _marker_filter(resource)}, first=5)

    assert result["data"] is None
    assert result["errors"][0]["message"] == "'search' cannot be combined with first"


def test_without_search_lists_page(test_client_graphql, seeded_rows, resource):
    result = _post(test_client_graphql, resource)

    assert "errors" not in result
    connection = result["data"][resource.field]
    assert connection["page"]
    assert connection["searchEdges"] == []
    assert connection["searchMetadata"] is None


SUBSCRIPTION_PROCESSES_QUERY = """
query SubscriptionProcesses($id: UUID!, $search: ResourceSearchInput) {
    subscription(id: $id) {
        processes(search: $search) {
            searchEdges {
                node {
                    processId
                }
            }
        }
    }
}
"""


def test_subscription_processes_search_is_scoped_to_its_processes(
    test_client_graphql, mocked_processes, generic_subscription_1
):
    related = set(
        db.session.scalars(
            select(ProcessTable.process_id).where(
                ProcessTable.process_subscriptions.any(subscription_id=UUID(generic_subscription_1))
            )
        )
    )
    db.session.add_all(
        [_index_row(EntityType.PROCESS, process_id, PROCESSES.path, "hit") for process_id in mocked_processes]
    )
    db.session.commit()

    variables = {"id": generic_subscription_1, "search": {"filters": _marker_filter(PROCESSES)}}
    data = json.dumps({"query": SUBSCRIPTION_PROCESSES_QUERY, "variables": variables})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS).json()

    assert "errors" not in response
    edges = response["data"]["subscription"]["processes"]["searchEdges"]
    assert {UUID(edge["node"]["processId"]) for edge in edges} == related
