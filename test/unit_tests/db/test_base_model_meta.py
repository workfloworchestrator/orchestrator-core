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

"""Unit tests for BaseModelMeta.query: deprecated, and must raise NoSessionError before set_query() is called."""

import pytest

from orchestrator.core.db.database import BaseModel, NoSessionError
from orchestrator.core.db.models import WorkflowTable


@pytest.fixture
def restore_query():
    # Read through __dict__: a bound query_property builds a Query on attribute access, and fails for abstract BaseModel.
    original = BaseModel.__dict__.get("_query")
    yield
    BaseModel.set_query(original)


def test_query_raises_no_session_error_before_set_query(restore_query):
    BaseModel.set_query(None)
    with pytest.warns(DeprecationWarning), pytest.raises(NoSessionError, match=r"call init_database\(\) first"):
        _ = WorkflowTable.query


def test_query_returns_value_after_set_query(restore_query):
    sentinel = object()
    BaseModel.set_query(sentinel)
    with pytest.warns(DeprecationWarning, match="legacy SQLAlchemy Query API"):
        assert WorkflowTable.query is sentinel
