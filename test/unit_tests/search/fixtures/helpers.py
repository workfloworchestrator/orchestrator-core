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

from types import SimpleNamespace
from unittest.mock import MagicMock

from orchestrator.core.search.aggregations import BaseAggregation
from orchestrator.core.search.core.types import BooleanOperator, FilterOp, UIType
from orchestrator.core.search.filters import EqualityFilter, FilterTree, PathFilter

SIMPLE_SUBSCRIPTION_FILTER = FilterTree(
    op=BooleanOperator.AND,
    children=[
        PathFilter(
            path="subscription.status",
            condition=EqualityFilter(op=FilterOp.EQ, value="active"),
            value_kind=UIType.STRING,
        ),
    ],
)


def make_search_row(entity_id: str, entity_title: str, score: float = 0.92) -> MagicMock:
    """Create a mock DB row matching what the search retriever returns."""
    row = MagicMock()
    row.entity_id = entity_id
    row.entity_title = entity_title
    row.score = score
    row.get = lambda key, default=None: {"entity_title": entity_title, "perfect_match": 0}.get(key, default)
    return row


def make_column_row(entity_id: str, columns: dict[str, str | None]) -> SimpleNamespace:
    """Create a fake DB row matching what the column pivot query returns.

    Converts field paths to aliases (e.g. 'subscription.status' -> 'subscription_status')
    just like the real SQL query does via BaseAggregation.field_to_alias.
    """
    attrs = {"entity_id": entity_id}
    for path, value in columns.items():
        alias = BaseAggregation.field_to_alias(path)
        attrs[alias] = value  # type: ignore[assignment]
    return SimpleNamespace(**attrs)
