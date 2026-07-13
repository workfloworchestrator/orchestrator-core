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

"""Tests that structured (filter-only) search resolves matching_field to the full indexed path.

Filtering on a global (dotless) field like ``status`` matches index rows by path suffix,
so the reported matching field must contain the full stored path (e.g. ``subscription.status``),
resolved per entity from the index rather than echoed from the filter input.
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy_utils import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import BooleanOperator, EntityType, FieldType, FilterOp, UIType
from orchestrator.core.search.filters import EqualityFilter, FilterTree, LtreeFilter, PathFilter
from orchestrator.core.search.query import engine
from orchestrator.core.search.query.queries import SelectQuery


def _index_row(entity_id: UUID, path: str, value: str, title: str) -> AiSearchIndex:
    return AiSearchIndex(
        entity_type=EntityType.SUBSCRIPTION,
        entity_id=entity_id,
        entity_title=title,
        path=Ltree(path),
        value=value,
        value_type=FieldType.STRING,
        content_hash=uuid4().hex,
    )


@pytest.fixture
def indexed_subscriptions() -> tuple[UUID, UUID]:
    """Two indexed subscriptions: one with a root-level status, one with only a nested block status."""
    sub_a, sub_b = uuid4(), uuid4()
    db.session.add_all(
        [
            _index_row(sub_a, "subscription.status", "active", title="sub a"),
            _index_row(sub_a, "subscription.description", "first subscription", title="sub a"),
            _index_row(sub_b, "subscription.block.status", "provisioning", title="sub b"),
            _index_row(sub_b, "subscription.description", "second subscription", title="sub b"),
        ]
    )
    db.session.commit()
    return sub_a, sub_b


def _eq_filter(path: str, value: str) -> FilterTree:
    return FilterTree(
        op=BooleanOperator.AND,
        children=[
            PathFilter(path=path, condition=EqualityFilter(op=FilterOp.EQ, value=value), value_kind=UIType.STRING)
        ],
    )


def _select_query(filters: FilterTree) -> SelectQuery:
    return SelectQuery(entity_type=EntityType.SUBSCRIPTION, filters=filters)


async def test_global_field_filter_returns_full_path(indexed_subscriptions):
    """Filtering on the global field 'status' reports the full indexed path, not the filter input."""
    sub_a, _ = indexed_subscriptions

    response = await engine.execute_search(_select_query(_eq_filter("status", "active")), db.session)

    assert [r.entity_id for r in response.results] == [str(sub_a)]
    fields = response.results[0].matching_fields
    assert len(fields) == 1
    assert fields[0].path == "subscription.status"
    assert fields[0].text == "active"


async def test_global_field_filter_resolves_path_per_entity(indexed_subscriptions):
    """The full path comes from the entity's own matched row, also for nested block fields."""
    _, sub_b = indexed_subscriptions

    response = await engine.execute_search(_select_query(_eq_filter("status", "provisioning")), db.session)

    assert [r.entity_id for r in response.results] == [str(sub_b)]
    fields = response.results[0].matching_fields
    assert len(fields) == 1
    assert fields[0].path == "subscription.block.status"
    assert fields[0].text == "provisioning"


async def test_full_path_filter_returns_full_path(indexed_subscriptions):
    """Filtering on an explicit full path keeps reporting that full path."""
    sub_a, _ = indexed_subscriptions

    response = await engine.execute_search(_select_query(_eq_filter("subscription.status", "active")), db.session)

    assert [r.entity_id for r in response.results] == [str(sub_a)]
    fields = response.results[0].matching_fields
    assert len(fields) == 1
    assert fields[0].path == "subscription.status"
    assert fields[0].text == "active"


async def test_ends_with_filter_returns_full_path_per_entity(indexed_subscriptions):
    """A path-only ends_with filter on 'status' resolves each entity's own full path and value."""
    sub_a, sub_b = indexed_subscriptions
    filters = FilterTree(
        op=BooleanOperator.AND,
        children=[
            PathFilter(
                path="*",
                condition=LtreeFilter(op=FilterOp.ENDS_WITH, value="status"),
                value_kind=UIType.COMPONENT,
            )
        ],
    )

    response = await engine.execute_search(_select_query(filters), db.session)

    matching_by_id = {r.entity_id: r.matching_fields for r in response.results}
    assert set(matching_by_id) == {str(sub_a), str(sub_b)}
    assert len(matching_by_id[str(sub_a)]) == 1
    assert matching_by_id[str(sub_a)][0].path == "subscription.status"
    assert matching_by_id[str(sub_a)][0].text == "active"
    assert len(matching_by_id[str(sub_b)]) == 1
    assert matching_by_id[str(sub_b)][0].path == "subscription.block.status"
    assert matching_by_id[str(sub_b)][0].text == "provisioning"


async def test_multi_leaf_filter_returns_all_matching_fields(indexed_subscriptions):
    """With multiple filter leaves, a MatchingField is returned for each positive leaf."""
    sub_a, _ = indexed_subscriptions
    filters = FilterTree(
        op=BooleanOperator.AND,
        children=[
            PathFilter(
                path="status", condition=EqualityFilter(op=FilterOp.EQ, value="active"), value_kind=UIType.STRING
            ),
            PathFilter(
                path="subscription.description",
                condition=EqualityFilter(op=FilterOp.EQ, value="first subscription"),
                value_kind=UIType.STRING,
            ),
        ],
    )

    response = await engine.execute_search(_select_query(filters), db.session)

    assert [r.entity_id for r in response.results] == [str(sub_a)]
    fields = response.results[0].matching_fields
    assert len(fields) == 2
    assert fields[0].path == "subscription.status"
    assert fields[0].text == "active"
    assert fields[1].path == "subscription.description"
    assert fields[1].text == "first subscription"
