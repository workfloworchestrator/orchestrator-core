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

"""Query-plan performance of the text retrievers against a seeded search index.

The fuzzy retriever finds its hits through the trigram index on the values, ranks them per entity and restricts them
to the entities the filters allow. The tests assert that no plan node runs more often than there are entities, and
snapshot what each scenario's statement costs Postgres in ``plan_metrics/retrievers.pg<major>.md``; see `_plans`.
"""

# TODO: Scenarios still to cover, when #1976 changes how fuzzy matches multiple terms: more terms, terms without
#  matches, and terms that match many values each.

from hashlib import md5
from uuid import UUID

import pytest
from sqlalchemy import text

from orchestrator.core.db import db
from orchestrator.core.search.core.types import EntityType, RetrieverType
from orchestrator.core.search.filters import FilterTree
from orchestrator.core.search.query.builder import build_candidate_query
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.search.retrieval.retrievers.base import Retriever
from test.integration_tests.search.performance._plans import (
    assert_no_node_runs_more_often_than,
    plan_metrics,
    plan_metrics_snapshot,
    plan_of,
    render_plan_metrics,
    seed_index,
)

pytestmark = pytest.mark.search

ENTITY_COUNT = 1000
# Paths per entity whose values match none of the query texts, so the trigram index has to tell them apart.
FILLER_PATHS = 20

# Descriptions combine a word of each list, so each word is shared by a fraction of the entities: the longer the
# list, the fewer. Entity ids are random-looking, as real ones: sequential ids are all trigram-similar to each other.
SEED_SQL = text(
    """
    INSERT INTO ai_search_index (entity_type, entity_id, entity_title, path, value, value_type, content_hash)
    SELECT 'SUBSCRIPTION', e.id, 'sub ' || e.n, f.path::ltree, f.value, f.value_type::field_type, md5(e.n || f.path)
    FROM (SELECT n, md5(n::text)::uuid AS id FROM generate_series(1, :entities) n) e
    CROSS JOIN LATERAL (VALUES
        ('subscription.subscription_id', e.id::text, 'uuid'),
        ('subscription.status', CASE WHEN e.n % 10 = 0 THEN 'terminated' ELSE 'active' END, 'string'),
        ('subscription.description',
         (ARRAY['Redundant', 'Dedicated', 'Managed', 'Shared', 'Virtual'])[e.n % 5 + 1] || ' '
         || (ARRAY['fiber', 'wavelength', 'ethernet', 'internet', 'firewall', 'tunnel', 'router'])[e.n % 7 + 1] || ' '
         || (ARRAY['Amsterdam', 'Utrecht', 'Groningen', 'Eindhoven', 'Rotterdam', 'Maastricht', 'Leiden', 'Zwolle',
                   'Arnhem', 'Nijmegen', 'Enschede'])[e.n % 11 + 1],
         'string')
    ) f(path, value, value_type)
    UNION ALL
    SELECT 'SUBSCRIPTION', md5(n::text)::uuid, 'sub ' || n, ('subscription.block.field_' || k)::ltree,
           'value ' || k, 'string', md5(n || 'x' || k)
    FROM generate_series(1, :entities) n, generate_series(1, :filler) k
    """
)


def _entity_id(n):
    return UUID(md5(str(n).encode(), usedforsecurity=False).hexdigest())


ACTIVE = {"path": "subscription.status", "condition": {"op": "eq", "value": "active"}, "value_kind": "string"}

# Each scenario's query text, retriever and filters.
FUZZY_SCENARIOS = [
    pytest.param("fiber", RetrieverType.FUZZY, None, id="fuzzy-one_term"),
    pytest.param("managed fiber utrecht", RetrieverType.FUZZY, None, id="fuzzy-three_terms"),
    # Shorter than a trigram: matched on the padded trigrams of word starts only.
    pytest.param("fi", RetrieverType.FUZZY, None, id="fuzzy-short_term"),
    # Never embedded, so routed to fuzzy without asking for it.
    pytest.param(str(_entity_id(42)), None, None, id="fuzzy-uuid"),
    pytest.param("fiber", RetrieverType.FUZZY, {"op": "AND", "children": [ACTIVE]}, id="fuzzy-one_term_and_status"),
]


@pytest.fixture
def seeded_index():
    seed_index(SEED_SQL, entities=ENTITY_COUNT, filler=FILLER_PATHS)


def _select_stmt(query_text, retriever, filters):
    query = SelectQuery(
        entity_type=EntityType.SUBSCRIPTION,
        query_text=query_text,
        retriever=retriever,
        filters=filters and FilterTree.model_validate(filters),
    )
    return Retriever.route(query, cursor=None).apply(build_candidate_query(query)).limit(query.limit)


@pytest.mark.parametrize("query_text,retriever,filters", FUZZY_SCENARIOS)
def test_fuzzy_runs_each_plan_node_at_most_once_per_entity(seeded_index, query_text, retriever, filters):
    stmt = _select_stmt(query_text, retriever, filters)

    assert db.session.connection().execute(stmt).all()
    assert_no_node_runs_more_often_than(plan_of(stmt), ENTITY_COUNT, "entities")


def test_fuzzy_finds_an_entity_by_its_id(seeded_index):
    rows = db.session.connection().execute(_select_stmt(str(_entity_id(42)), None, None)).all()

    assert (rows[0].entity_id, rows[0].highlight_path) == (_entity_id(42), "subscription.subscription_id")


def test_plan_metrics_are_unchanged(seeded_index):
    scenarios = {scenario.id: [plan_metrics(plan_of(_select_stmt(*scenario.values)))] for scenario in FUZZY_SCENARIOS}
    page = render_plan_metrics(
        "Retriever plan metrics",
        f"{ENTITY_COUNT:,} subscriptions with {FILLER_PATHS + 3} index rows each, among which an id and a description "
        "of three words. Each scenario is the first page of a search with that query text.",
        scenarios,
    )
    assert page == plan_metrics_snapshot("retrievers")
