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
from uuid import uuid4

import pytest
from graphql import GraphQLError
from strawberry.types.nodes import SelectedField

from orchestrator.core.graphql.resource_search import _reject_non_search_arguments, search_resource
from orchestrator.core.graphql.search_inputs import ResourceSearchInput
from orchestrator.core.search.core.exceptions import (
    InvalidCursorError,
    InvalidSearchPageError,
    QueryStateNotFoundError,
)
from orchestrator.core.search.core.types import EntityType, SearchMetadata
from orchestrator.core.search.query.exceptions import PathNotFoundError
from orchestrator.core.search.query.page import SearchPage
from orchestrator.core.search.query.results import MatchingField, SearchResponse, SearchResult

EXECUTE_SEARCH_PAGE = "orchestrator.core.graphql.resource_search.execute_search_page"


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


async def _search(search_page, load_nodes, search=None, first=10, after=0):
    with patch(EXECUTE_SEARCH_PAGE, AsyncMock(return_value=search_page)):
        return await search_resource(
            _info(), EntityType.SUBSCRIPTION, search or ResourceSearchInput(), load_nodes, first=first, after=after
        )


@pytest.mark.parametrize(
    "next_page_cursor, search, after, has_previous_page",
    [
        pytest.param(None, ResourceSearchInput(), 0, False, id="single-page"),
        pytest.param("next", ResourceSearchInput(), 0, False, id="first-of-more"),
        pytest.param(None, ResourceSearchInput(), 10, True, id="last-of-more-by-offset"),
        pytest.param(None, ResourceSearchInput(cursor="previous"), 0, True, id="last-of-more-by-cursor"),
    ],
)
async def test_search_resource_page_info(next_page_cursor, search, after, has_previous_page):
    entity_id = str(uuid4())
    search_page = _page(_result(entity_id), next_page_cursor=next_page_cursor)

    connection = await _search(search_page, AsyncMock(return_value={entity_id: "node"}), search=search, after=after)

    assert connection.next_page_cursor == next_page_cursor
    assert connection.page == ["node"]
    assert connection.page_info.has_next_page is (next_page_cursor is not None)
    assert connection.page_info.has_previous_page is has_previous_page


async def test_search_resource_keeps_ranking_and_skips_hits_without_entity():
    """The search index can lag behind deletions, so a hit whose entity no longer loads is dropped."""
    first, deleted, second = (str(uuid4()) for _ in range(3))
    search_page = _page(_result(first, 0.9), _result(deleted, 0.8), _result(second, 0.7))

    connection = await _search(search_page, AsyncMock(return_value={second: "second", first: "first"}))

    assert connection.page == ["first", "second"]
    assert [edge.score for edge in connection.search_edges] == [0.9, 0.7]


async def test_search_resource_without_hits_does_not_load_nodes():
    load_nodes = AsyncMock()

    connection = await _search(_page(), load_nodes)

    assert connection.page == []
    load_nodes.assert_not_called()


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
        pytest.param(InvalidSearchPageError("Missing input"), "VALIDATION_ERROR", None, id="missing-input"),
        pytest.param(ValueError("Invalid query"), "VALIDATION_ERROR", None, id="invalid-query"),
        pytest.param(PathNotFoundError("subscription.x"), "VALIDATION_ERROR", None, id="query-validation"),
        pytest.param(QueryStateNotFoundError("Query not found"), "NOT_FOUND", None, id="query-not-found"),
        pytest.param(RuntimeError("runtime error"), "INTERNAL_ERROR", "Search failed: runtime error", id="unexpected"),
    ],
)
async def test_search_resource_maps_errors(error, code, message):
    with patch(EXECUTE_SEARCH_PAGE, AsyncMock(side_effect=error)):
        with pytest.raises(GraphQLError) as exc_info:
            await search_resource(
                _info(), EntityType.SUBSCRIPTION, ResourceSearchInput(), AsyncMock(), first=10, after=0
            )

    assert exc_info.value.extensions["code"] == code
    assert exc_info.value.message == (message or str(error))


async def test_search_resource_maps_invalid_page_size():
    """The page size is validated while building the query, inside the same error mapping."""
    with pytest.raises(GraphQLError) as exc_info:
        await search_resource(_info(), EntityType.SUBSCRIPTION, ResourceSearchInput(), AsyncMock(), first=0, after=0)

    assert exc_info.value.extensions["code"] == "VALIDATION_ERROR"
