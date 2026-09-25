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

from unittest import mock

import pytest
from sqlalchemy.orm import as_declarative

from orchestrator.core.db.database import BaseModelMeta, NoSessionError, SearchQuery


@as_declarative(metaclass=BaseModelMeta)
class ModelWithoutQuery:
    """Stand-in for a model hierarchy on which set_query() was never called."""

    __abstract__ = True


def test_query_raises_no_session_error_when_set_query_never_called() -> None:
    with pytest.raises(NoSessionError, match="init_database"):
        _ = ModelWithoutQuery.query


def test_query_returns_query_after_set_query() -> None:
    sentinel = mock.Mock(spec=SearchQuery)
    ModelWithoutQuery.set_query(sentinel)
    assert ModelWithoutQuery.query is sentinel


def test_query_is_inherited_by_subclasses() -> None:
    class ChildModel(ModelWithoutQuery):
        __abstract__ = True

    assert ChildModel.query is ModelWithoutQuery.query
