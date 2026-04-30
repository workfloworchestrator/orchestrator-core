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

"""Tests for orchestrator.core.search.query.state -- QueryState loading from UUID/string, error handling, and limit clamping."""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from orchestrator.core.search.core.exceptions import QueryStateNotFoundError
from orchestrator.core.search.query.queries import BaseQuery, SelectQuery
from orchestrator.core.search.query.state import QueryState

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
        "orchestrator.core.search.query.state.db.session.query",
        return_value=MagicMock(filter_by=MagicMock(return_value=MagicMock(first=MagicMock(return_value=return_value)))),
    )


# =============================================================================
# load_from_id -- UUID object
# =============================================================================


def test_load_from_uuid_object_returns_query_state():
    mock_row = _make_mock_search_query()
    with _patch_db_first(mock_row):
        state = QueryState.load_from_id(_QUERY_UUID, SelectQuery)
    assert isinstance(state, QueryState)
    assert isinstance(state.query, SelectQuery)


def test_load_from_uuid_object_query_embedding_none():
    mock_row = _make_mock_search_query(query_embedding=None)
    with _patch_db_first(mock_row):
        state = QueryState.load_from_id(_QUERY_UUID, SelectQuery)
    assert state.query_embedding is None


def test_load_from_uuid_object_query_embedding_list():
    embedding = [0.1, 0.2, 0.3]
    mock_row = _make_mock_search_query(query_embedding=embedding)
    with _patch_db_first(mock_row):
        state = QueryState.load_from_id(_QUERY_UUID, SelectQuery)
    assert state.query_embedding == embedding


# =============================================================================
# load_from_id -- string UUID
# =============================================================================


def test_load_from_string_uuid_returns_query_state():
    mock_row = _make_mock_search_query()
    with _patch_db_first(mock_row):
        state = QueryState.load_from_id(_QUERY_UUID_STR, SelectQuery)
    assert isinstance(state, QueryState)
    assert isinstance(state.query, SelectQuery)


def test_load_from_string_uuid_embedding_round_trips():
    embedding = [1.0, 2.0, 3.0]
    mock_row = _make_mock_search_query(query_embedding=embedding)
    with _patch_db_first(mock_row):
        state = QueryState.load_from_id(_QUERY_UUID_STR, SelectQuery)
    assert state.query_embedding == embedding


# =============================================================================
# load_from_id -- invalid format
# =============================================================================


@pytest.mark.parametrize(
    "bad_id",
    [
        pytest.param("not-a-uuid", id="random-string"),
        pytest.param("12345", id="numeric-string"),
        pytest.param("", id="empty-string"),
        pytest.param("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", id="wrong-hex"),
        pytest.param(None, id="none-value"),
    ],
)
def test_load_from_invalid_format_raises(bad_id):
    with pytest.raises((ValueError, TypeError)):
        QueryState.load_from_id(bad_id, SelectQuery)


# =============================================================================
# load_from_id -- not found in DB
# =============================================================================


def test_load_not_found_raises_query_state_not_found_error():
    with _patch_db_first(None):
        with pytest.raises(QueryStateNotFoundError):
            QueryState.load_from_id(_QUERY_UUID, SelectQuery)


def test_load_not_found_error_message_contains_uuid():
    with _patch_db_first(None):
        with pytest.raises(QueryStateNotFoundError, match=str(_QUERY_UUID)):
            QueryState.load_from_id(_QUERY_UUID, SelectQuery)


# =============================================================================
# load_from_id -- limit clamping
# =============================================================================


@pytest.mark.parametrize(
    "limit,expected_limit",
    [
        pytest.param(BaseQuery.MAX_LIMIT + 100, BaseQuery.MAX_LIMIT, id="oversized-clamped"),
        pytest.param(BaseQuery.MAX_LIMIT, BaseQuery.MAX_LIMIT, id="exact-max-not-clamped"),
        pytest.param(BaseQuery.MAX_LIMIT - 5, BaseQuery.MAX_LIMIT - 5, id="below-max-not-clamped"),
    ],
)
def test_load_limit_clamping(limit: int, expected_limit: int):
    params = {**_MINIMAL_PARAMS, "limit": limit}
    mock_row = _make_mock_search_query(parameters=params)
    with _patch_db_first(mock_row):
        state = QueryState.load_from_id(_QUERY_UUID, SelectQuery)
    assert state.query.limit == expected_limit


def test_load_parameters_without_limit_key_uses_default():
    """Parameters dict without 'limit' key should use the default limit."""
    mock_row = _make_mock_search_query(parameters=_MINIMAL_PARAMS)
    with _patch_db_first(mock_row):
        state = QueryState.load_from_id(_QUERY_UUID, SelectQuery)
    assert state.query.limit == BaseQuery.DEFAULT_LIMIT
