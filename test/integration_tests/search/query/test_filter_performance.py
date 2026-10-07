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

"""Query-plan performance of structured filters against a seeded search index.

The index has one row per (entity, path), so a filter evaluated per index row instead of per entity
costs paths-per-entity times too much. Wall-clock time is too noisy to assert on, so the tests assert via
``EXPLAIN ANALYZE`` that no plan node runs more often than there are entities. They benchmark with
walltime because the work runs inside Postgres, invisible to CodSpeed's simulation.
"""

import asyncio
from contextlib import contextmanager
from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from more_itertools import one
from sqlalchemy import event, text

from orchestrator.core.db import db
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.filters import FilterTree
from orchestrator.core.search.query.builder import build_candidate_query, build_simple_count_query
from orchestrator.core.search.query.engine import execute_search
from orchestrator.core.search.query.mixins import OrderDirection, StructuredOrderBy
from orchestrator.core.search.query.queries import CountQuery, SelectQuery
from orchestrator.core.search.retrieval.pagination import PageCursor
from orchestrator.core.search.retrieval.retrievers.base import Retriever

pytestmark = pytest.mark.search

ENTITY_COUNT = 1000
# Unfiltered paths per entity; with the four filterable ones they set the index-rows-per-entity ratio.
FILLER_PATHS = 20

SEED_SQL = text(
    """
    INSERT INTO ai_search_index (entity_type, entity_id, entity_title, path, value, value_type, content_hash)
    SELECT 'SUBSCRIPTION', e.id, 'sub ' || e.n, f.path::ltree, f.value, f.value_type::field_type, md5(e.n || f.path)
    FROM (SELECT n, lpad(to_hex(n), 32, '0')::uuid AS id FROM generate_series(1, :entities) n) e
    CROSS JOIN LATERAL (VALUES
        ('subscription.status', CASE WHEN e.n % 10 = 0 THEN 'terminated' ELSE 'active' END, 'string'),
        ('subscription.customer_id', 'cust' || (e.n % 50), 'string'),
        ('subscription.start_date', (DATE '2024-01-01' + e.n % 700)::text, 'datetime'),
        ('subscription.port.speed', ((e.n % 4 + 1) * 1000)::text, 'integer')
    ) f(path, value, value_type)
    UNION ALL
    SELECT 'SUBSCRIPTION', lpad(to_hex(n), 32, '0')::uuid, 'sub ' || n, ('subscription.block.field_' || k)::ltree,
           'v' || k, 'string', md5(n || 'x' || k)
    FROM generate_series(1, :entities) n, generate_series(1, :filler) k
    UNION ALL
    SELECT 'SUBSCRIPTION', lpad(to_hex(n), 32, '0')::uuid, 'sub ' || n, 'subscription.node.name'::ltree,
           'node' || n, 'string', md5(n || 'node')
    FROM generate_series(1, :entities) n WHERE n % 3 = 0
    """
)


def _entity_id(n):
    return UUID(int=n)


def _status(n):
    return "terminated" if n % 10 == 0 else "active"


def _customer_id(n):
    return f"cust{n % 50}"


def _start_date(n):
    return (date(2024, 1, 1) + timedelta(days=n % 700)).isoformat()


def _port_speed(n):
    return (n % 4 + 1) * 1000


def _has_node(n):
    return n % 3 == 0


ACTIVE = {"path": "subscription.status", "condition": {"op": "eq", "value": "active"}, "value_kind": "string"}
CUST7 = {"path": "subscription.customer_id", "condition": {"op": "eq", "value": "cust7"}, "value_kind": "string"}
# Dotless path: matched as `path ~ '*.speed'`, so one leaf uses an lquery instead of an exact path.
FAST = {"path": "speed", "condition": {"op": "gt", "value": 3000}, "value_kind": "number"}
# Entities with no `node` segment in any path: those not divisible by 3.
NO_NODE = {"path": "node", "condition": {"op": "not_has_component"}, "value_kind": "component"}

# For tests that need only one filter shape.
STATUS_AND_SPEED_OR_CUSTOMER = {"op": "AND", "children": [ACTIVE, {"op": "OR", "children": [FAST, CUST7]}]}


def _matches_status_and_speed_or_customer(n):
    return _status(n) == "active" and (_port_speed(n) > 3000 or _customer_id(n) == "cust7")


FILTER_SHAPES = [
    pytest.param(
        {"op": "AND", "children": [ACTIVE, CUST7]},
        lambda n: _status(n) == "active" and _customer_id(n) == "cust7",
        id="status_and_customer",
    ),
    pytest.param(
        {"op": "OR", "children": [FAST, CUST7]},
        lambda n: _port_speed(n) > 3000 or _customer_id(n) == "cust7",
        id="speed_or_customer",
    ),
    pytest.param(
        STATUS_AND_SPEED_OR_CUSTOMER,
        _matches_status_and_speed_or_customer,
        id="status_and_nested_speed_or_customer",
        marks=pytest.mark.xfail(strict=True, reason="EXISTS under OR inside AND is re-run per index row"),
    ),
    pytest.param(
        {"op": "OR", "children": [{"op": "AND", "children": [ACTIVE, FAST]}, CUST7]},
        lambda n: (_status(n) == "active" and _port_speed(n) > 3000) or _customer_id(n) == "cust7",
        id="nested_status_and_speed_or_customer",
    ),
    pytest.param(
        {"op": "AND", "children": [NO_NODE]},
        lambda n: not _has_node(n),
        id="no_node",
    ),
    pytest.param(
        {"op": "AND", "children": [ACTIVE, NO_NODE]},
        lambda n: _status(n) == "active" and not _has_node(n),
        id="status_and_no_node",
        marks=pytest.mark.xfail(strict=True, reason="NOT EXISTS inside AND is re-run per index row"),
    ),
    pytest.param(
        {"op": "OR", "children": [CUST7, NO_NODE]},
        lambda n: _customer_id(n) == "cust7" or not _has_node(n),
        id="customer_or_no_node",
    ),
]


@pytest.fixture
def seeded_index():
    # The trigger maintains ai_search_paths, which these tests never read; bypassing it halves the seed
    # time. ALTER TABLE is transactional, so the per-test rollback re-enables it.
    db.session.execute(text("ALTER TABLE ai_search_index DISABLE TRIGGER ai_search_paths_maintain_trg"))
    db.session.execute(SEED_SQL, {"entities": ENTITY_COUNT, "filler": FILLER_PATHS})
    # Without fresh statistics the planner guesses at row counts and the plan shape is arbitrary.
    db.session.execute(text("ANALYZE ai_search_index"))


def _matching(matches):
    return [n for n in range(1, ENTITY_COUNT + 1) if matches(n)]


@contextmanager
def _capturing_plans():
    """Run EXPLAIN ANALYZE next to every SELECT, with the statement's own compiled SQL and bound parameters.

    The plan is read from the raw cursor: through SQLAlchemy, the statement's result processors would
    be applied to the EXPLAIN output.
    """
    conn = db.session.connection()
    plans = []

    def explain(_conn, cursor, statement, parameters, _context, _executemany):
        # Session bookkeeping (SAVEPOINT, SET) cannot be explained and has no plan worth bounding.
        if statement.lstrip().upper().startswith("SELECT"):
            cursor.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {statement}", parameters)
            plans.append(cursor.fetchone()[0][0]["Plan"])

    event.listen(conn, "before_cursor_execute", explain)
    try:
        yield plans
    finally:
        event.remove(conn, "before_cursor_execute", explain)


def _plan_nodes(node):
    yield node
    for child in node.get("Plans", []):
        yield from _plan_nodes(child)


def _plan(stmt):
    """The plan of `stmt`, from an execution of its own so it never adds to a benchmark."""
    with _capturing_plans() as plans:
        db.session.connection().execute(stmt).all()
    return one(plans)


def _assert_no_node_runs_per_index_row(plan):
    busiest = max(_plan_nodes(plan), key=lambda node: node["Actual Loops"])
    name = " ".join(filter(None, [busiest["Node Type"], busiest.get("Subplan Name"), busiest.get("Relation Name")]))
    assert busiest["Actual Loops"] <= ENTITY_COUNT, (
        f"{name} ran {busiest['Actual Loops']} times for {ENTITY_COUNT} entities"
    )


def _select_query(filters, limit=SelectQuery.DEFAULT_LIMIT):
    # Ordered, so the order_value subquery is part of the measured plan.
    return SelectQuery(
        entity_type=EntityType.SUBSCRIPTION,
        filters=FilterTree.model_validate(filters),
        order_by=StructuredOrderBy(element="subscription.start_date", direction=OrderDirection.DESC),
        limit=limit,
    )


def _count_stmt(filters):
    query = CountQuery(entity_type=EntityType.SUBSCRIPTION, filters=FilterTree.model_validate(filters))
    return build_simple_count_query(build_candidate_query(query))


@pytest.mark.parametrize("filters,matches", FILTER_SHAPES)
def test_select_runs_each_plan_node_at_most_once_per_entity(seeded_index, benchmark_walltime, filters, matches):
    query = _select_query(filters)
    stmt = Retriever.route(query, cursor=None).apply(build_candidate_query(query)).limit(query.limit)
    conn = db.session.connection()

    @benchmark_walltime
    def rows():
        return conn.execute(stmt).all()

    # Two stable sorts: start_date descending, ties broken by entity_id ascending, as the retriever orders.
    by_id = sorted(_matching(matches), key=_entity_id)
    expected_page = sorted(by_id, key=_start_date, reverse=True)[: query.limit]
    assert [(row.entity_id, row.order_value) for row in rows] == [
        (_entity_id(n), _start_date(n)) for n in expected_page
    ]
    _assert_no_node_runs_per_index_row(_plan(stmt))


@pytest.mark.xfail(strict=True, reason="count(distinct) references the inner query, adding it as a second FROM")
def test_count_runs_each_plan_node_at_most_once_per_entity(seeded_index, benchmark_walltime):
    """The count query wraps the candidate query."""
    stmt = _count_stmt(STATUS_AND_SPEED_OR_CUSTOMER)
    conn = db.session.connection()

    @benchmark_walltime
    def total_count():
        return conn.execute(stmt).scalar_one()

    assert total_count == len(_matching(_matches_status_and_speed_or_customer))
    # Counting a column of the inner query instead of its subquery would make SQLAlchemy emit both: a cartesian product.
    assert len(stmt.get_final_froms()) == 1
    _assert_no_node_runs_per_index_row(_plan(stmt))


@pytest.mark.xfail(strict=True, reason="EXISTS under OR inside AND is re-run per index row")
@pytest.mark.parametrize("page", [pytest.param(1, id="page_1"), pytest.param(2, id="page_2")])
def test_search_total_count_runs_each_plan_node_at_most_once_per_entity(
    seeded_index, async_session, benchmark_walltime, page
):
    """The search endpoint counts all matches, and from page 2 on also the matches from the cursor on."""
    total = len(_matching(_matches_status_and_speed_or_customer))
    # With half of the matches per page, page 2 exists as long as the filter matches at least two entities.
    query = _select_query(STATUS_AND_SPEED_OR_CUSTOMER, limit=min(SelectQuery.MAX_LIMIT, max(1, total // 2)))
    cursor = None
    if page == 2:
        last = asyncio.run(execute_search(query, async_session)).results[-1]
        cursor = PageCursor(score=last.score, id=last.entity_id, query_id=uuid4(), order_value=last.order_value)

    @benchmark_walltime
    def response():
        return asyncio.run(execute_search(query, async_session, cursor=cursor))

    assert response.total_items == total
    assert response.start_cursor == (page - 1) * query.limit

    with _capturing_plans() as plans:
        asyncio.run(execute_search(query, async_session, cursor=cursor))
    for plan in plans:
        _assert_no_node_runs_per_index_row(plan)
