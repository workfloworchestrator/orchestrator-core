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

"""Unit tests for BaseModelMeta.query: must raise NoSessionError before set_query() is called."""

import pytest

from orchestrator.core.db.database import BaseModel, NoSessionError
from orchestrator.core.db.models import WorkflowTable


def test_query_raises_no_session_error_before_set_query():
    with pytest.raises(NoSessionError, match=r"call init_database\(\) first"):
        _ = WorkflowTable.query


def test_query_returns_value_after_set_query():
    sentinel = object()
    BaseModel.set_query(sentinel)
    assert WorkflowTable.query is sentinel
    BaseModel.set_query(None)
