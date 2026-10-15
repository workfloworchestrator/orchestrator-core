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
"""Unit tests for the shared `search` machinery of the GraphQL list resources.

What needs the search index or a saved query is covered in test/integration_tests/graphql/test_resources_search.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from graphql import GraphQLError
from strawberry.types.nodes import SelectedField

from orchestrator.core.graphql.resource_search import (
    _reject_non_search_arguments,
    execute_resource_search,
    to_search_connection,
)
from orchestrator.core.graphql.search_inputs import ResourceSearchInput
from orchestrator.core.search.core.exceptions import InvalidCursorError, QueryStateNotFoundError
from orchestrator.core.search.core.types import EntityType, SearchMetadata
from orchestrator.core.search.query.page import SearchPage
from orchestrator.core.search.query.results import MatchingField, SearchResponse, SearchResult


def _info(repeat=1, **arguments):
    field = SelectedField(name="subscriptions", directives={}, arguments=arguments, alias=None, selections=[])
    return MagicMock(selected_fields=[field] * repeat)


def _result(entity_id, score=1.0):
    return SearchResult(
        entity_id=entity_id,
        entity_type=EntityType.SUBSCRIPTION,
        entity_title=entity_id,
        score=score,
        perfect_match=1,
        matching_fields=[MatchingField(text="active", path="subscription.status", highlight_indices=[(0, 6)])],
    )


def _page(*results, next_page_cursor=None):
    response = SearchResponse(
        results=list(results), metadata=SearchMetadata.structured(), total_items=len(results), start_cursor=0
    )
    return SearchPage(response=response, next_page_cursor=next_page_cursor)


@pytest.mark.parametrize(
    "next_page_cursor, has_previous_page",
    [
        pytest.param(None, False, id="single-page"),
        pytest.param("cursor", False, id="first-of-more"),
        pytest.param(None, True, id="last-of-more"),
    ],
)
def test_to_search_connection_page_info(next_page_cursor, has_previous_page):
    search_page = _page(_result("a"), next_page_cursor=next_page_cursor)

    connection = to_search_connection(search_page, {"a": "node a"}, has_previous_page=has_previous_page)

    assert connection.next_page_cursor == next_page_cursor
    assert connection.page_info.has_next_page is (next_page_cursor is not None)
    assert connection.page_info.has_previous_page is has_previous_page


@pytest.mark.parametrize(
    "arguments, conflicting",
    [
        pytest.param({"filterBy": [{"field": "status", "value": "active"}]}, "filterBy", id="filterBy"),
        pytest.param({"sortBy": [{"field": "startDate", "order": "ASC"}]}, "sortBy", id="sortBy"),
        pytest.param({"query": "active"}, "query", id="query"),
        pytest.param({"query": "active", "filterBy": []}, "filterBy, query", id="multiple"),
    ],
)
def test_search_combined_with_other_arguments_is_rejected(arguments, conflicting):
    with pytest.raises(GraphQLError) as exc_info:
        _reject_non_search_arguments(_info(search={}, **arguments))

    assert exc_info.value.message == f"'search' cannot be combined with {conflicting}"
    assert exc_info.value.extensions["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("repeat", [pytest.param(1, id="single"), pytest.param(2, id="repeated-field")])
def test_arguments_sent_as_null_are_not_rejected(repeat):
    _reject_non_search_arguments(_info(repeat=repeat, search={}, filterBy=None, sortBy=None, query=None, first=10))


def test_repeated_field_combined_with_other_arguments_is_rejected():
    """A field selected twice without alias is merged into one resolver call that sees both selections."""
    with pytest.raises(GraphQLError) as exc_info:
        _reject_non_search_arguments(_info(repeat=2, search={}, query="active"))

    assert exc_info.value.message == "'search' cannot be combined with query"


@pytest.mark.parametrize(
    "error, code, message",
    [
        pytest.param(InvalidCursorError("Invalid pagination cursor"), "VALIDATION_ERROR", None, id="invalid-cursor"),
        pytest.param(ValueError("Invalid query"), "VALIDATION_ERROR", None, id="invalid-query"),
        pytest.param(QueryStateNotFoundError("Query not found"), "NOT_FOUND", None, id="query-not-found"),
        pytest.param(RuntimeError("runtime error"), "INTERNAL_ERROR", "Search failed: runtime error", id="unexpected"),
    ],
)
async def test_execute_resource_search_maps_errors(error, code, message):
    with patch("orchestrator.core.graphql.resource_search.execute_search_page", AsyncMock(side_effect=error)):
        with pytest.raises(GraphQLError) as exc_info:
            await execute_resource_search(_info(), EntityType.SUBSCRIPTION, ResourceSearchInput(), first=10, after=0)

    assert exc_info.value.extensions["code"] == code
    assert exc_info.value.message == (message or str(error))


async def test_execute_resource_search_maps_invalid_page_size():
    """The page size is validated while building the query, inside the same error mapping."""
    with pytest.raises(GraphQLError) as exc_info:
        await execute_resource_search(_info(), EntityType.SUBSCRIPTION, ResourceSearchInput(), first=0, after=0)

    assert exc_info.value.extensions["code"] == "VALIDATION_ERROR"
