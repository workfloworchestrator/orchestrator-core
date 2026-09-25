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


def _model_without_query() -> type:
    """A fresh model hierarchy on which set_query() was never called.

    set_query() stores the query on the class, so each test needs its own
    declarative base to stay independent of test execution order.
    """

    @as_declarative(metaclass=BaseModelMeta)
    class ModelWithoutQuery:
        __abstract__ = True

    return ModelWithoutQuery


def test_query_raises_no_session_error_when_set_query_never_called() -> None:
    with pytest.raises(NoSessionError, match="init_database"):
        _ = _model_without_query().query


def test_query_returns_query_after_set_query() -> None:
    model = _model_without_query()
    sentinel = mock.Mock(spec=SearchQuery)
    model.set_query(sentinel)
    assert model.query is sentinel


def test_query_is_inherited_by_subclasses() -> None:
    model = _model_without_query()
    sentinel = mock.Mock(spec=SearchQuery)
    model.set_query(sentinel)

    class ChildModel(model):
        __abstract__ = True

    assert ChildModel.query is sentinel
