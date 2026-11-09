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
Which retriever a hybrid text match came from is covered in test_hybrid_union.py.
"""

from uuid import uuid4

import pytest

from orchestrator.core.db import db
from orchestrator.core.search.core.types import EntityType, RetrieverType
from orchestrator.core.search.filters import FilterTree
from orchestrator.core.search.query import engine
from orchestrator.core.search.query.queries import SelectQuery
from test.integration_tests.search.retrieval._helpers import and_tree, eq_leaf, index_row, vec

QUERY_TEXT = "Coffee grinder CG-2000-XL"


class Seeded:
    exact = uuid4()  # its own description is the query text
    close = uuid4()  # a near match, ranked below `exact` by every retriever
    terminated = uuid4()  # matches the text as well, but fails the status filter


@pytest.fixture
def seeded() -> type[Seeded]:
    db.session.add_all(
        [
            index_row(Seeded.exact, "subscription.description", QUERY_TEXT, "exact", vec(0)),
            index_row(Seeded.exact, "subscription.status", "active", "exact"),
            index_row(Seeded.exact, "subscription.customer.name", "Acme", "exact"),
            index_row(Seeded.close, "subscription.description", "Coffee grinder CG-2000-XS", "close", vec(1)),
            index_row(Seeded.close, "subscription.status", "active", "close"),
            index_row(Seeded.close, "subscription.customer.name", "Acme", "close"),
            index_row(Seeded.terminated, "subscription.description", QUERY_TEXT, "terminated", vec(0)),
            index_row(Seeded.terminated, "subscription.status", "terminated", "terminated"),
        ]
    )
    db.session.commit()
    return Seeded


RETRIEVERS = [
    pytest.param(RetrieverType.FUZZY, None, id="fuzzy"),
    pytest.param(RetrieverType.SEMANTIC, vec(0), id="semantic"),
    pytest.param(RetrieverType.HYBRID, vec(0), id="hybrid"),
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


@pytest.mark.parametrize("retriever,embedding", RETRIEVERS)
async def test_text_match_first_then_filter_matches(seeded, async_session, retriever, embedding):
    """Each result reports the field that matched the text, then every field that satisfied a filter."""
    filters = and_tree(eq_leaf("subscription.status", "active"), eq_leaf("subscription.customer.name", "Acme"))

    response = await _search(filters, retriever, embedding, async_session)

    fields_by_id = {r.entity_id: [(f.path, f.text) for f in r.matching_fields] for r in response.results}
    assert fields_by_id[str(seeded.exact)] == [
        ("subscription.description", QUERY_TEXT),
        ("subscription.status", "active"),
        ("subscription.customer.name", "Acme"),
    ]
    assert str(seeded.terminated) not in fields_by_id


@pytest.mark.parametrize("retriever,embedding", RETRIEVERS)
async def test_filter_matches_keep_ranked_order_and_limit(seeded, async_session, retriever, embedding):
    """Adding the filter matches keeps the ranking and the page size of the text search."""
    filters = and_tree(eq_leaf("subscription.status", "active"))

    full = await _search(filters, retriever, embedding, async_session)
    first = await _search(filters, retriever, embedding, async_session, limit=1)

    assert [r.entity_id for r in full.results] == [str(seeded.exact), str(seeded.close)]
    assert [r.score for r in full.results] == sorted((r.score for r in full.results), reverse=True)
    assert [r.entity_id for r in first.results] == [str(seeded.exact)]
    assert first.has_more is True
