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

"""response_columns must restore the indexed value_type instead of returning every value as text."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy_utils import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import BooleanOperator, EntityType, FieldType, FilterOp, UIType
from orchestrator.core.search.filters import EqualityFilter, FilterTree, PathFilter
from orchestrator.core.search.query import engine
from orchestrator.core.search.query.queries import SelectQuery

TYPED_FIELDS: dict[str, tuple[str, FieldType]] = {
    "subscription.status": ("active", FieldType.STRING),
    "subscription.insync": ("False", FieldType.BOOLEAN),
    "subscription.port.speed": ("1000", FieldType.INTEGER),
    "subscription.port.ratio": ("0.5", FieldType.FLOAT),
    "subscription.start_date": ("2026-08-28 13:20:14.955529+00:00", FieldType.DATETIME),
}


@pytest.fixture
def indexed_subscription() -> UUID:
    sub = uuid4()
    db.session.add_all(
        [
            AiSearchIndex(
                entity_type=EntityType.SUBSCRIPTION,
                entity_id=sub,
                entity_title="typed sub",
                path=Ltree(path),
                value=value,
                value_type=value_type,
                content_hash=uuid4().hex,
            )
            for path, (value, value_type) in TYPED_FIELDS.items()
        ]
    )
    db.session.commit()
    return sub


@pytest.mark.parametrize(
    "path,expected",
    [
        pytest.param("subscription.status", "active", id="string-stays-string"),
        pytest.param("subscription.insync", False, id="boolean-becomes-bool"),
        pytest.param("subscription.port.speed", 1000, id="integer-becomes-int"),
        pytest.param("subscription.port.ratio", 0.5, id="float-becomes-float"),
        pytest.param("subscription.start_date", "2026-08-28 13:20:14.955529+00:00", id="datetime-stays-string"),
    ],
)
async def test_response_columns_restore_indexed_types(indexed_subscription, path, expected):
    filters = FilterTree(
        op=BooleanOperator.AND,
        children=[
            PathFilter(
                path="subscription.status",
                condition=EqualityFilter(op=FilterOp.EQ, value="active"),
                value_kind=UIType.STRING,
            )
        ],
    )
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, filters=filters, response_columns=[path])

    response = await engine.execute_search(query, db.session)

    (result,) = [r for r in response.results if r.entity_id == str(indexed_subscription)]
    assert result.response_columns == {path: expected}
    assert type(result.response_columns[path]) is type(expected)
