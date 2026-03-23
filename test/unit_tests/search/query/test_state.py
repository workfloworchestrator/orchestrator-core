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

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from orchestrator.search.core.exceptions import QueryStateNotFoundError
from orchestrator.search.query.queries import BaseQuery, SelectQuery
from orchestrator.search.query.state import QueryState

pytestmark = pytest.mark.search

_QUERY_UUID = UUID("12345678-1234-1234-1234-123456789abc")
_QUERY_UUID_STR = str(_QUERY_UUID)

_MINIMAL_PARAMS: dict = {"entity_type": "SUBSCRIPTION", "query_type": "select"}


def _make_mock_search_query(
    parameters: dict | None = None,
    query_embedding: list[float] | None = None,
) -> MagicMock:
    """Build a mock SearchQueryTable row."""
    mock = MagicMock()
    mock.parameters = dict(parameters or _MINIMAL_PARAMS)
    mock.query_embedding = query_embedding
    return mock


def _patch_db_first(return_value):
    """Return a context manager that patches the db query chain used by QueryState.load_from_id."""
    return patch(
        "orchestrator.search.query.state.db.session.query",
        return_value=MagicMock(filter_by=MagicMock(return_value=MagicMock(first=MagicMock(return_value=return_value)))),
    )


# =============================================================================
# load_from_id – UUID object
# =============================================================================


class TestQueryStateLoadFromUUID:
    """Tests using a UUID object as query_id."""

    def test_uuid_object_returns_query_state(self) -> None:
        mock_row = _make_mock_search_query()
        with _patch_db_first(mock_row):
            state = QueryState.load_from_id(_QUERY_UUID, SelectQuery)

        assert isinstance(state, QueryState)
        assert isinstance(state.query, SelectQuery)

    def test_uuid_object_query_embedding_none(self) -> None:
        mock_row = _make_mock_search_query(query_embedding=None)
        with _patch_db_first(mock_row):
            state = QueryState.load_from_id(_QUERY_UUID, SelectQuery)

        assert state.query_embedding is None

    def test_uuid_object_query_embedding_list(self) -> None:
        embedding = [0.1, 0.2, 0.3]
        mock_row = _make_mock_search_query(query_embedding=embedding)
        with _patch_db_first(mock_row):
            state = QueryState.load_from_id(_QUERY_UUID, SelectQuery)

        assert state.query_embedding == embedding


# =============================================================================
# load_from_id – string UUID
# =============================================================================


class TestQueryStateLoadFromStringUUID:
    """Tests using a string representation of a UUID as query_id."""

    def test_string_uuid_returns_query_state(self) -> None:
        mock_row = _make_mock_search_query()
        with _patch_db_first(mock_row):
            state = QueryState.load_from_id(_QUERY_UUID_STR, SelectQuery)

        assert isinstance(state, QueryState)
        assert isinstance(state.query, SelectQuery)

    def test_string_uuid_embedding_round_trips(self) -> None:
        embedding = [1.0, 2.0, 3.0]
        mock_row = _make_mock_search_query(query_embedding=embedding)
        with _patch_db_first(mock_row):
            state = QueryState.load_from_id(_QUERY_UUID_STR, SelectQuery)

        assert state.query_embedding == embedding


# =============================================================================
# load_from_id – invalid format
# =============================================================================


class TestQueryStateInvalidFormat:
    """Tests for invalid query_id formats."""

    @pytest.mark.parametrize(
        "bad_id",
        ["not-a-uuid", "12345", "", "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", None],
        ids=["random-string", "numeric-string", "empty-string", "wrong-hex", "none-value"],
    )
    def test_invalid_format_raises_value_error(self, bad_id) -> None:
        with pytest.raises((ValueError, TypeError)):
            QueryState.load_from_id(bad_id, SelectQuery)


# =============================================================================
# load_from_id – not found in DB
# =============================================================================


class TestQueryStateNotFound:
    """Tests for a query_id that has no matching DB row."""

    def test_not_found_raises_query_state_not_found_error(self) -> None:
        with _patch_db_first(None):
            with pytest.raises(QueryStateNotFoundError):
                QueryState.load_from_id(_QUERY_UUID, SelectQuery)

    def test_not_found_error_message_contains_uuid(self) -> None:
        with _patch_db_first(None):
            with pytest.raises(QueryStateNotFoundError, match=str(_QUERY_UUID)):
                QueryState.load_from_id(_QUERY_UUID, SelectQuery)


# =============================================================================
# load_from_id – limit clamping
# =============================================================================


class TestQueryStateLimitClamping:
    """Tests for the MAX_LIMIT clamping behaviour."""

    def test_oversized_limit_clamped_to_max(self) -> None:
        oversized_limit = BaseQuery.MAX_LIMIT + 100
        params = {**_MINIMAL_PARAMS, "limit": oversized_limit}
        mock_row = _make_mock_search_query(parameters=params)

        with _patch_db_first(mock_row):
            state = QueryState.load_from_id(_QUERY_UUID, SelectQuery)

        assert state.query.limit == BaseQuery.MAX_LIMIT

    def test_exact_max_limit_not_clamped(self) -> None:
        params = {**_MINIMAL_PARAMS, "limit": BaseQuery.MAX_LIMIT}
        mock_row = _make_mock_search_query(parameters=params)

        with _patch_db_first(mock_row):
            state = QueryState.load_from_id(_QUERY_UUID, SelectQuery)

        assert state.query.limit == BaseQuery.MAX_LIMIT

    def test_limit_below_max_not_clamped(self) -> None:
        limit = BaseQuery.MAX_LIMIT - 5
        params = {**_MINIMAL_PARAMS, "limit": limit}
        mock_row = _make_mock_search_query(parameters=params)

        with _patch_db_first(mock_row):
            state = QueryState.load_from_id(_QUERY_UUID, SelectQuery)

        assert state.query.limit == limit

    def test_parameters_without_limit_key_pass_through(self) -> None:
        """Parameters dict without 'limit' key should not be modified."""
        mock_row = _make_mock_search_query(parameters=_MINIMAL_PARAMS)

        with _patch_db_first(mock_row):
            state = QueryState.load_from_id(_QUERY_UUID, SelectQuery)

        # Default limit should apply
        assert state.query.limit == BaseQuery.DEFAULT_LIMIT
