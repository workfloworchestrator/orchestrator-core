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

import json
from http import HTTPStatus
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from more_itertools import one

from test.integration_tests.config import GRAPHQL_ENDPOINT, GRAPHQL_HEADERS

SEARCH_QUERY = """
query SearchQuery($entityType: EntityType!, $input: SearchInput!) {
    search(entityType: $entityType, input: $input) {
        data {
            entityId
            entityType
            entityTitle
            score
            perfectMatch
            matchingFields {
                text
                path
                highlightIndices
            }
            responseColumns
        }
        pageInfo {
            hasNextPage
            nextPageCursor
        }
        searchMetadata {
            searchType
            description
        }
        cursor {
            totalItems
            startCursor
            endCursor
        }
    }
}
"""

SEARCH_PATHS_QUERY = """
query SearchPathsQuery($prefix: String, $q: String, $entityType: EntityType, $limit: Int) {
    searchPaths(prefix: $prefix, q: $q, entityType: $entityType, limit: $limit) {
        leaves {
            name
            uiTypes
            paths
        }
        components {
            name
            uiTypes
        }
    }
}
"""

SEARCH_DEFINITIONS_QUERY = """
query SearchDefinitionsQuery {
    searchDefinitions {
        uiType
        operators
        valueSchema {
            operator
            kind
            fields {
                operator
                kind
            }
        }
    }
}
"""

SEARCH_QUERY_BY_ID = """
query SearchQueryById($queryId: String!, $cursor: String) {
    searchQuery(queryId: $queryId, cursor: $cursor) {
        data {
            entityId
            entityType
            entityTitle
            score
        }
        pageInfo {
            hasNextPage
            nextPageCursor
        }
        searchMetadata {
            searchType
            description
        }
    }
}
"""

SEARCH_QUERY_RESULTS = """
query SearchQueryResults($queryId: String!) {
    searchQueryResults(queryId: $queryId) {
        results {
            groupValues {
                key
                value
            }
            aggregations {
                key
                value
            }
        }
        totalResults
        metadata {
            searchType
            description
        }
        visualizationType {
            type
        }
    }
}
"""

SEARCH_QUERY_EXPORT = """
query SearchQueryExport($queryId: String!) {
    searchQueryExport(queryId: $queryId) {
        page
    }
}
"""


def test_search_definitions_query(test_client_graphql) -> None:
    data = json.dumps({"query": SEARCH_DEFINITIONS_QUERY})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    definitions = result["data"]["searchDefinitions"]
    assert isinstance(definitions, list)
    assert len(definitions) > 0
    for defn in definitions:
        assert "uiType" in defn
        assert "operators" in defn
        assert isinstance(defn["operators"], list)
        assert "valueSchema" in defn


@pytest.mark.search
def test_search_paths_query(test_client_graphql) -> None:
    data = json.dumps({"query": SEARCH_PATHS_QUERY, "variables": {"entityType": "SUBSCRIPTION", "limit": 5}})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    paths_data = result["data"]["searchPaths"]
    assert "leaves" in paths_data
    assert "components" in paths_data
    assert isinstance(paths_data["leaves"], list)
    assert isinstance(paths_data["components"], list)


@pytest.mark.search
def test_search_subscriptions(test_client_graphql) -> None:
    data = json.dumps(
        {
            "query": SEARCH_QUERY,
            "variables": {"entityType": "SUBSCRIPTION", "input": {"limit": 5}},
        }
    )
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    search_data = result["data"]["search"]
    assert "data" in search_data
    assert "pageInfo" in search_data
    assert isinstance(search_data["data"], list)


@pytest.mark.search
def test_search_with_filters(test_client_graphql) -> None:
    data = json.dumps(
        {
            "query": SEARCH_QUERY,
            "variables": {
                "entityType": "SUBSCRIPTION",
                "input": {
                    "limit": 5,
                    "filters": {
                        "op": "AND",
                        "filters": [
                            {
                                "path": "subscription.status",
                                "condition": {"op": "EQ", "value": "active"},
                                "valueKind": "STRING",
                            }
                        ],
                    },
                },
            },
        }
    )
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    search_data = result["data"]["search"]
    assert isinstance(search_data["data"], list)


@pytest.mark.search
def test_search_with_text_query(test_client_graphql) -> None:
    fake_embedding = [0.0] * 1536
    data = json.dumps(
        {
            "query": SEARCH_QUERY,
            "variables": {
                "entityType": "SUBSCRIPTION",
                "input": {"query": "fiber", "limit": 5},
            },
        }
    )
    with patch(
        "orchestrator.core.search.core.embedding.QueryEmbedder.generate_for_text_async",
        new=AsyncMock(return_value=fake_embedding),
    ):
        response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    search_data = result["data"]["search"]
    assert isinstance(search_data["data"], list)


@pytest.mark.search
@pytest.mark.parametrize("entity_type", ["SUBSCRIPTION", "PRODUCT", "WORKFLOW", "PROCESS"])
def test_search_all_entity_types(test_client_graphql, entity_type: str) -> None:
    data = json.dumps(
        {
            "query": SEARCH_QUERY,
            "variables": {"entityType": entity_type, "input": {"limit": 3}},
        }
    )
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    search_data = result["data"]["search"]
    assert isinstance(search_data["data"], list)
    assert "pageInfo" in search_data


def test_search_invalid_input_returns_validation_error(test_client_graphql) -> None:
    """The query is built inside the error mapping, so invalid input is not masked as an internal error."""
    data = json.dumps({"query": SEARCH_QUERY, "variables": {"entityType": "SUBSCRIPTION", "input": {"filters": {}}}})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)

    assert response.status_code == HTTPStatus.OK
    error = one(response.json()["errors"])
    assert "FilterTreeInput must contain at least one filter or group" in error["message"]
    assert error["extensions"]["code"] == "VALIDATION_ERROR"


def test_search_query_not_found(test_client_graphql) -> None:
    query_id = str(uuid4())
    data = json.dumps({"query": SEARCH_QUERY_BY_ID, "variables": {"queryId": query_id}})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" in result
    assert len(result["errors"]) > 0


def test_search_query_results_not_found(test_client_graphql) -> None:
    query_id = str(uuid4())
    data = json.dumps({"query": SEARCH_QUERY_RESULTS, "variables": {"queryId": query_id}})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" in result
    assert len(result["errors"]) > 0


def test_search_query_export_not_found(test_client_graphql) -> None:
    query_id = str(uuid4())
    data = json.dumps({"query": SEARCH_QUERY_EXPORT, "variables": {"queryId": query_id}})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" in result
    assert len(result["errors"]) > 0


@pytest.mark.search
def test_search_invalid_limit(test_client_graphql) -> None:
    data = json.dumps(
        {
            "query": SEARCH_PATHS_QUERY,
            "variables": {"entityType": "SUBSCRIPTION", "limit": 100},
        }
    )
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    paths_data = result["data"]["searchPaths"]
    assert isinstance(paths_data["leaves"], list)
    assert isinstance(paths_data["components"], list)
