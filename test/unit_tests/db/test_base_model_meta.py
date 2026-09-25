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

"""Tests for BaseModelMeta.query raising NoSessionError when the DB is not initialized."""

from unittest.mock import MagicMock

import pytest

from orchestrator.core.db.database import BaseModel, NoSessionError, SearchQuery


def test_query_raises_no_session_error_when_unset():
    """Accessing .query before set_query/init_database must raise NoSessionError, not AttributeError."""
    previous = object()
    had_query = hasattr(BaseModel, "_query")
    if had_query:
        previous = BaseModel._query
        delattr(BaseModel, "_query")

    try:
        with pytest.raises(NoSessionError, match="init_database"):
            _ = BaseModel.query
    finally:
        if had_query:
            BaseModel._query = previous
        elif hasattr(BaseModel, "_query"):
            delattr(BaseModel, "_query")


def test_query_returns_set_query():
    """After set_query, .query returns the configured SearchQuery."""
    previous = object()
    had_query = hasattr(BaseModel, "_query")
    if had_query:
        previous = BaseModel._query

    mock_query = MagicMock(spec=SearchQuery)
    try:
        BaseModel.set_query(mock_query)
        assert BaseModel.query is mock_query
    finally:
        if had_query:
            BaseModel._query = previous
        elif hasattr(BaseModel, "_query"):
            delattr(BaseModel, "_query")
