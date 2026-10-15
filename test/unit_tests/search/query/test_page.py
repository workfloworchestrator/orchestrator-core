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
"""Unit tests for the validation in `execute_search_page`; each case raises before the search engine runs."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from orchestrator.core.search.core.exceptions import InvalidCursorError
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.query.page import execute_search_page
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.search.query.state import QueryState
from orchestrator.core.search.retrieval.pagination import PageCursor

OFFSET_MESSAGE = "An offset only works for structured search (filters without query text); page with a cursor"


def _cursor():
    return PageCursor(score=1.0, id=str(uuid4()), query_id=uuid4()).encode()


@pytest.mark.parametrize(
    "kwargs, message",
    [
        pytest.param({"cursor": "cursor", "offset": 2}, "Page with either an offset or a cursor, not both", id="both"),
        pytest.param(
            {"query": SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text="active"), "offset": 2},
            OFFSET_MESSAGE,
            id="offset-with-query-text",
        ),
        pytest.param({}, "Either query, cursor or query_id must be provided", id="nothing-to-search"),
    ],
)
async def test_invalid_paging_raises(kwargs, message):
    with pytest.raises(ValueError) as exc_info:
        await execute_search_page(MagicMock(), **kwargs)

    assert str(exc_info.value) == message


async def test_malformed_cursor_raises():
    with pytest.raises(InvalidCursorError):
        await execute_search_page(MagicMock(), cursor="not-a-cursor")


async def test_cursor_of_other_entity_type_raises():
    """A cursor only references a saved query, so without this check it would page another entity's search."""
    saved = QueryState(query=SelectQuery(entity_type=EntityType.PROCESS), query_embedding=None)

    with patch.object(QueryState, "load_from_id", AsyncMock(return_value=saved)):
        with pytest.raises(InvalidCursorError, match="Cursor belongs to a PROCESS search"):
            await execute_search_page(MagicMock(), cursor=_cursor(), entity_type=EntityType.SUBSCRIPTION)


async def test_query_without_criteria_returns_no_hits_and_no_cursor():
    page = await execute_search_page(MagicMock(), query=SelectQuery(entity_type=EntityType.SUBSCRIPTION))

    assert page.entity_ids == []
    assert page.next_page_cursor is None
