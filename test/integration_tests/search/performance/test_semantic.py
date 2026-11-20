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

"""Query-plan shape of the bounded semantic retriever against a seeded search index.

The bounded plan must read its window from the per-type HNSW index rather than sort every vector of the type.
It asserts on plan nodes without overriding planner settings, as HNSW block counts vary per backend.
"""

import pytest
from sqlalchemy import text

from orchestrator.core.db import db
from orchestrator.core.search.core.types import EntityType, RetrieverType
from orchestrator.core.search.query.builder import build_candidate_query
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.search.retrieval.retrievers.semantic import SemanticRetriever
from orchestrator.core.settings import llm_settings
from test.integration_tests.search.performance._plans import PLAN_SETTINGS, plan_nodes, plan_of_statement

pytestmark = pytest.mark.search

# About 6k distinct texts over 50k rows, more than ANALYZE samples, so the planner works from estimates as in
# production. More vectors would only add setup time.
ENTITY_COUNT = 5000
# About 1.5% of the distinct texts. Above about 2% pgvector prefers sorting every vector, so the test would
# check the cost model.
WINDOW = 90
HNSW_INDEX = "ix_ai_search_embeddings_hnsw_subscription"

# Low-cardinality fields repeat one text over many entities. Rows are written directly as the indexer needs an
# embedding API.
SEED_SQL = text(
    """
    WITH indexed AS (
        INSERT INTO ai_search_index
            (entity_type, entity_id, entity_title, path, value, value_type, content_hash, embedding_hash)
        SELECT 'SUBSCRIPTION', md5(n::text)::uuid, 'sub ' || n, f.path::ltree, f.value, 'string', md5(n || f.path),
               md5(f.path || ': ' || f.value)
        FROM generate_series(1, :entities) n
        CROSS JOIN LATERAL (VALUES
            ('subscription.description', 'description ' || n),
            ('subscription.status', CASE WHEN n % 10 = 0 THEN 'terminated' WHEN n % 10 = 1 THEN 'provisioning'
                                         ELSE 'active' END),
            ('subscription.product.name', 'product ' || n % 30),
            ('subscription.customer.name', 'customer ' || n % 500),
            ('subscription.location', 'location ' || n % 200),
            ('subscription.block.field_1', 'a' || n % 50),
            ('subscription.block.field_2', 'b' || n % 50),
            ('subscription.block.field_3', 'c' || n % 50),
            ('subscription.block.field_4', 'd' || n % 50),
            ('subscription.block.field_5', 'e' || n % 50)
        ) f(path, value)
        RETURNING embedding_hash
    )
    INSERT INTO ai_search_embeddings (entity_type, embedding_hash, embedding)
    SELECT 'SUBSCRIPTION', texts.embedding_hash, vector.embedding
    FROM (SELECT DISTINCT embedding_hash FROM indexed) texts
    -- The reference to texts makes Postgres draw a vector per text instead of one for all of them.
    CROSS JOIN LATERAL (
        SELECT array_agg(random() - 0.5)::vector AS embedding
        FROM generate_series(1, :dimension)
        WHERE texts.embedding_hash IS NOT NULL
    ) vector
    """
)


@pytest.fixture
def seeded_vectors():
    db.session.execute(text("ALTER TABLE ai_search_index DISABLE TRIGGER ai_search_paths_maintain_trg"))
    # Building the index over the seeded vectors is several times faster than inserting them into it one by one.
    definition = db.session.execute(
        text("SELECT pg_get_indexdef(:index ::regclass)"), {"index": HNSW_INDEX}
    ).scalar_one()
    db.session.execute(text(f"DROP INDEX {HNSW_INDEX}"))
    db.session.execute(SEED_SQL, {"entities": ENTITY_COUNT, "dimension": llm_settings.EMBEDDING_DIMENSION})
    db.session.execute(text(definition))
    # Without statistics the planner guesses the tables' sizes and the plan shape is arbitrary.
    db.session.execute(text("ANALYZE ai_search_index"))
    db.session.execute(text("ANALYZE ai_search_embeddings"))
    for name, value in PLAN_SETTINGS.items():  # a side effect per setting, not a collection that is built
        db.session.execute(text("SELECT set_config(:name, :value, true)"), {"name": name, "value": value})


def test_unfiltered_window_is_read_from_the_hnsw_index(seeded_vectors):
    """Sorting every vector of the type instead reads the whole table per search, however small the window."""
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text="active", retriever=RetrieverType.SEMANTIC)
    vector = db.session.execute(
        text(
            "SELECT embedding::text FROM ai_search_embeddings WHERE embedding_hash = md5('subscription.status: active')"
        )
    ).scalar_one()
    retriever = SemanticRetriever(
        [float(v) for v in vector.strip("[]").split(",")], None, EntityType.SUBSCRIPTION, candidates_limit=WINDOW
    )

    plan = plan_of_statement(retriever.apply(build_candidate_query(query)).limit(query.limit))

    assert ("Index Scan", HNSW_INDEX) in {(node["Node Type"], node.get("Index Name")) for node in plan_nodes(plan)}
