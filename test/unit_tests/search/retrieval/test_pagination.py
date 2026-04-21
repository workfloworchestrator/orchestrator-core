"""Tests for PageCursor encode/decode roundtrips and encode_next_page_cursor logic.

Covers cursor serialization, URL-safe base64 encoding, error handling for invalid
cursors, first-page vs subsequent-page cursor generation, and DB persistence behavior.
"""

# Copyright 2019-2025 SURF, GÉANT.
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

import base64
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from orchestrator.core.search.core.exceptions import InvalidCursorError
from orchestrator.core.search.core.types import EntityType, SearchMetadata
from orchestrator.core.search.query.results import SearchResponse, SearchResult
from orchestrator.core.search.retrieval.pagination import PageCursor, encode_next_page_cursor

pytestmark = pytest.mark.search

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_UUID = UUID("12345678-1234-5678-1234-567812345678")
_SAMPLE_SCORE = 0.95
_SAMPLE_ENTITY_ID = "aabbccdd-0000-0000-0000-000000000001"


def _make_page_cursor(
    score: float = _SAMPLE_SCORE,
    entity_id: str = _SAMPLE_ENTITY_ID,
    query_id: UUID = _SAMPLE_UUID,
) -> PageCursor:
    return PageCursor(score=score, id=entity_id, query_id=query_id)


def _make_search_result(entity_id: str = _SAMPLE_ENTITY_ID, score: float = 0.8) -> SearchResult:
    return SearchResult(
        entity_id=entity_id,
        entity_type=EntityType.SUBSCRIPTION,
        entity_title="Test Entity",
        score=score,
    )


def _make_search_response(
    results: list[SearchResult],
    has_more: bool = True,
    query_embedding: list[float] | None = None,
) -> SearchResponse:
    metadata = SearchMetadata(search_type="fuzzy", description="test search")
    return SearchResponse(
        results=results,
        metadata=metadata,
        has_more=has_more,
        query_embedding=query_embedding,
    )


# ---------------------------------------------------------------------------
# PageCursor encode / decode roundtrip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "score,entity_id,query_id",
    [
        pytest.param(
            0.95,
            "aabbccdd-0000-0000-0000-000000000001",
            UUID("12345678-1234-5678-1234-567812345678"),
            id="typical_values",
        ),
        pytest.param(
            0.0,
            "00000000-0000-0000-0000-000000000000",
            UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
            id="zero_score_boundary_uuid",
        ),
        pytest.param(
            1.0,
            "deadbeef-dead-beef-dead-beefdeadbeef",
            uuid4(),
            id="max_score_random_uuid",
        ),
    ],
)
def test_encode_decode_roundtrip(score, entity_id, query_id):
    """Test that encoding and decoding a PageCursor preserves all fields."""
    cursor = PageCursor(score=score, id=entity_id, query_id=query_id)
    encoded = cursor.encode()
    decoded = PageCursor.decode(encoded)

    assert decoded.score == cursor.score
    assert decoded.id == cursor.id
    assert decoded.query_id == cursor.query_id


def test_encode_produces_url_safe_base64():
    """URL-safe base64 must not contain '+' or '/'."""
    cursor = _make_page_cursor()
    encoded = cursor.encode()
    assert "+" not in encoded
    assert "/" not in encoded


def test_encode_is_valid_base64():
    """Encoded cursor must be decodable as urlsafe_b64decode without error."""
    cursor = _make_page_cursor()
    encoded = cursor.encode()
    decoded_bytes = base64.urlsafe_b64decode(encoded)
    assert len(decoded_bytes) > 0


# ---------------------------------------------------------------------------
# PageCursor.decode error paths
# ---------------------------------------------------------------------------

BAD_CURSORS = [
    pytest.param("not-valid-base64!!!", id="invalid_base64"),
    pytest.param("aGVsbG8=", id="valid_base64_invalid_json"),
    pytest.param(base64.urlsafe_b64encode(b'{"score": 1.0}').decode(), id="missing_required_fields"),
    pytest.param("", id="empty_string"),
    pytest.param("   ", id="whitespace_only"),
    pytest.param("thisIsNotBase64OrJson_____!!!", id="random_string"),
]


@pytest.mark.parametrize("bad_cursor", BAD_CURSORS)
def test_invalid_cursor_raises_invalid_cursor_error(bad_cursor):
    """Invalid cursor strings must raise InvalidCursorError."""
    with pytest.raises(InvalidCursorError):
        PageCursor.decode(bad_cursor)


# ---------------------------------------------------------------------------
# encode_next_page_cursor — no more results
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cursor",
    [
        pytest.param(None, id="no_existing_cursor"),
        pytest.param(_make_page_cursor(), id="with_existing_cursor"),
    ],
)
def test_has_more_false_returns_none(cursor):
    """When has_more is False, encode_next_page_cursor returns None regardless of cursor."""
    result_item = _make_search_result()
    response = _make_search_response([result_item], has_more=False)
    query_mock = MagicMock()

    result = encode_next_page_cursor(response, cursor=cursor, query=query_mock)

    assert result is None


# ---------------------------------------------------------------------------
# encode_next_page_cursor — first page
# ---------------------------------------------------------------------------


def test_first_page_saves_query_and_returns_cursor():
    """First page persists search query to DB and returns a valid cursor."""
    result_item = _make_search_result(entity_id="entity-abc-001", score=0.75)
    response = _make_search_response([result_item], has_more=True, query_embedding=[0.1, 0.2, 0.3])
    query_mock = MagicMock()
    saved_query_id = uuid4()

    mock_search_query = MagicMock()
    mock_search_query.query_id = saved_query_id

    with (
        patch("orchestrator.search.retrieval.pagination.SearchQueryTable") as mock_table,
        patch("orchestrator.search.retrieval.pagination.db") as mock_db,
        patch("orchestrator.search.query.state.QueryState"),
    ):
        mock_table.from_state.return_value = mock_search_query
        encoded = encode_next_page_cursor(response, cursor=None, query=query_mock)

    assert encoded is not None
    mock_db.session.add.assert_called_once_with(mock_search_query)
    mock_db.session.commit.assert_called_once()

    decoded = PageCursor.decode(encoded)
    assert decoded.query_id == saved_query_id
    assert decoded.id == "entity-abc-001"
    assert decoded.score == pytest.approx(0.75)


def test_first_page_uses_last_result_for_cursor():
    """First page cursor is built from the last result in the list."""
    results = [
        _make_search_result(entity_id="first-entity", score=0.9),
        _make_search_result(entity_id="last-entity", score=0.5),
    ]
    response = _make_search_response(results, has_more=True)
    query_mock = MagicMock()
    saved_query_id = uuid4()

    mock_search_query = MagicMock()
    mock_search_query.query_id = saved_query_id

    with (
        patch("orchestrator.search.retrieval.pagination.SearchQueryTable") as mock_table,
        patch("orchestrator.search.retrieval.pagination.db"),
        patch("orchestrator.search.query.state.QueryState"),
    ):
        mock_table.from_state.return_value = mock_search_query
        encoded = encode_next_page_cursor(response, cursor=None, query=query_mock)

    decoded = PageCursor.decode(encoded)
    assert decoded.id == "last-entity"
    assert decoded.score == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# encode_next_page_cursor — subsequent pages
# ---------------------------------------------------------------------------


def test_subsequent_page_reuses_cursor_query_id():
    """Subsequent pages reuse the existing cursor query_id without DB operations."""
    existing_query_id = uuid4()
    existing_cursor = _make_page_cursor(query_id=existing_query_id)
    result_item = _make_search_result(entity_id="next-entity", score=0.6)
    response = _make_search_response([result_item], has_more=True)
    query_mock = MagicMock()

    with (
        patch("orchestrator.search.retrieval.pagination.SearchQueryTable") as mock_table,
        patch("orchestrator.search.retrieval.pagination.db") as mock_db,
    ):
        encoded = encode_next_page_cursor(response, cursor=existing_cursor, query=query_mock)

    mock_db.session.add.assert_not_called()
    mock_db.session.commit.assert_not_called()
    mock_table.from_state.assert_not_called()

    decoded = PageCursor.decode(encoded)
    assert decoded.query_id == existing_query_id
    assert decoded.id == "next-entity"
    assert decoded.score == pytest.approx(0.6)


def test_subsequent_page_ignores_query_argument():
    """The query argument is not used on subsequent pages -- only cursor.query_id matters."""
    existing_query_id = uuid4()
    existing_cursor = _make_page_cursor(query_id=existing_query_id)
    result_item = _make_search_result()
    response = _make_search_response([result_item], has_more=True)
    different_query_mock = MagicMock()

    with (
        patch("orchestrator.search.retrieval.pagination.SearchQueryTable"),
        patch("orchestrator.search.retrieval.pagination.db"),
    ):
        encoded = encode_next_page_cursor(response, cursor=existing_cursor, query=different_query_mock)

    decoded = PageCursor.decode(encoded)
    assert decoded.query_id == existing_query_id
