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

"""A text search with filters reports the text match first, then the fields that satisfied the filters.

The text ranking decides the order and the highlighted field; the filters only restrict the candidates.
Every text retriever must still report the filter matches of each result, after its text match.
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy_utils import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import (
    BooleanOperator,
    EntityType,
    FieldType,
    FilterOp,
    RetrieverType,
    UIType,
)
from orchestrator.core.search.filters import EqualityFilter, FilterTree, LtreeFilter, PathFilter
from orchestrator.core.search.query import engine
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.settings import llm_settings

QUERY_TEXT = "Coffee grinder CG-2000-XL"


def _vec(axis: int) -> list[float]:
    vector = [0.0] * llm_settings.EMBEDDING_DIMENSION
    vector[axis] = 1.0
    return vector


def _index_row(
    entity_id: UUID, path: str, value: str, title: str, embedding: list[float] | None = None
) -> AiSearchIndex:
    return AiSearchIndex(
        entity_type=EntityType.SUBSCRIPTION,
        entity_id=entity_id,
        entity_title=title,
        path=Ltree(path),
        value=value,
        value_type=FieldType.STRING,
        content_hash=uuid4().hex,
        embedding=embedding,
    )


class Seeded:
    exact = uuid4()  # its own description is the query text
    close = uuid4()  # a near match, ranked below `exact` by every retriever
    terminated = uuid4()  # matches the text as well, but fails the status filter


@pytest.fixture
def seeded() -> type[Seeded]:
    db.session.add_all(
        [
            _index_row(Seeded.exact, "subscription.description", QUERY_TEXT, "exact", _vec(0)),
            _index_row(Seeded.exact, "subscription.status", "active", "exact"),
            _index_row(Seeded.exact, "subscription.customer.name", "Acme", "exact"),
            _index_row(Seeded.close, "subscription.description", "Coffee grinder CG-2000-XS", "close", _vec(1)),
            _index_row(Seeded.close, "subscription.status", "active", "close"),
            _index_row(Seeded.close, "subscription.customer.name", "Acme", "close"),
            _index_row(Seeded.terminated, "subscription.description", QUERY_TEXT, "terminated", _vec(0)),
            _index_row(Seeded.terminated, "subscription.status", "terminated", "terminated"),
        ]
    )
    db.session.commit()
    return Seeded


def _eq_leaf(path: str, value: str) -> PathFilter:
    return PathFilter(path=path, condition=EqualityFilter(op=FilterOp.EQ, value=value), value_kind=UIType.STRING)


def _and(*leaves: PathFilter) -> FilterTree:
    return FilterTree(op=BooleanOperator.AND, children=list(leaves))


RETRIEVERS = [
    pytest.param(RetrieverType.FUZZY, None, id="fuzzy"),
    pytest.param(RetrieverType.SEMANTIC, _vec(0), id="semantic"),
    pytest.param(RetrieverType.HYBRID, _vec(0), id="hybrid"),
]


async def _search(filters: FilterTree, retriever: RetrieverType, embedding: list[float] | None, session, limit=10):
    query = SelectQuery(
        entity_type=EntityType.SUBSCRIPTION,
        query_text=QUERY_TEXT,
        retriever=retriever,
        filters=filters,
        limit=limit,
    )
    return await engine.execute_search(query, session, query_embedding=embedding)


def _fields_by_id(response) -> dict[str, list[tuple[str, str]]]:
    return {r.entity_id: [(f.path, f.text) for f in r.matching_fields] for r in response.results}


@pytest.mark.parametrize("retriever,embedding", RETRIEVERS)
async def test_text_match_first_then_filter_matches(seeded, async_session, retriever, embedding):
    """Each result reports the field that matched the text, then every field that satisfied a filter."""
    filters = _and(_eq_leaf("subscription.status", "active"), _eq_leaf("subscription.customer.name", "Acme"))

    response = await _search(filters, retriever, embedding, async_session)

    assert _fields_by_id(response)[str(seeded.exact)] == [
        ("subscription.description", QUERY_TEXT),
        ("subscription.status", "active"),
        ("subscription.customer.name", "Acme"),
    ]
    assert str(seeded.terminated) not in _fields_by_id(response)


@pytest.mark.parametrize("retriever,embedding", RETRIEVERS)
async def test_field_matching_text_and_filter_is_reported_once(seeded, async_session, retriever, embedding):
    """A filter on the field the text matched adds no second entry for that field."""
    filters = _and(_eq_leaf("subscription.description", QUERY_TEXT), _eq_leaf("subscription.status", "active"))

    response = await _search(filters, retriever, embedding, async_session)

    assert _fields_by_id(response) == {
        str(seeded.exact): [("subscription.description", QUERY_TEXT), ("subscription.status", "active")]
    }


@pytest.mark.parametrize("retriever,embedding", RETRIEVERS)
async def test_existence_filter_adds_no_matching_fields(seeded, async_session, retriever, embedding):
    """has_component holds for every result, so only the text match is reported."""
    filters = _and(
        PathFilter(
            path="*", condition=LtreeFilter(op=FilterOp.HAS_COMPONENT, value="customer"), value_kind=UIType.COMPONENT
        )
    )

    response = await _search(filters, retriever, embedding, async_session)

    assert _fields_by_id(response)[str(seeded.exact)] == [("subscription.description", QUERY_TEXT)]


@pytest.mark.parametrize("retriever,embedding", RETRIEVERS)
async def test_filter_matches_keep_ranked_order_and_limit(seeded, async_session, retriever, embedding):
    """Adding the filter matches keeps the ranking and the page size of the text search."""
    filters = _and(_eq_leaf("subscription.status", "active"))

    full = await _search(filters, retriever, embedding, async_session)
    first = await _search(filters, retriever, embedding, async_session, limit=1)

    assert [r.entity_id for r in full.results] == [str(seeded.exact), str(seeded.close)]
    assert [r.score for r in full.results] == sorted((r.score for r in full.results), reverse=True)
    assert [r.entity_id for r in first.results] == [str(seeded.exact)]
    assert first.has_more is True
