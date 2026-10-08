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
costs paths-per-entity times too much. CodSpeed's simulation counts only this process's instructions,
not the work inside Postgres, and wall-clock time is too noisy to compare. The work Postgres does is
deterministic, though: with the same data, statistics and settings, ``EXPLAIN (ANALYZE, BUFFERS)``
reports the same plan, blocks and rows on every run. So the tests assert that no plan node runs more
often than there are entities, and snapshot per scenario what each statement cost Postgres, so that a
change in that cost shows up as a diff. Update the snapshots with ``pytest --inline-snapshot=fix``.
"""

import asyncio
from contextlib import contextmanager
from datetime import date, timedelta
from functools import partial
from uuid import UUID, uuid4

import pytest
from inline_snapshot import snapshot
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

# Settings the plans depend on that could differ per server or run: parallel workers split the work
# unpredictably and JIT kicks in on cost thresholds. work_mem decides between in-memory and on-disk sorts.
PLAN_SETTINGS = {"max_parallel_workers_per_gather": "0", "jit": "off", "work_mem": "4MB"}


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
    # Rows of earlier tests are rolled back but stay on their pages until vacuumed, which would change the blocks
    # read. TRUNCATE gives the seed fresh files, and like ALTER TABLE it is transactional: the per-test rollback
    # restores the table and re-enables the trigger.
    db.session.execute(text("TRUNCATE ai_search_index"))
    # The trigger maintains ai_search_paths, which these tests never read; bypassing it halves the seed time.
    db.session.execute(text("ALTER TABLE ai_search_index DISABLE TRIGGER ai_search_paths_maintain_trg"))
    db.session.execute(SEED_SQL, {"entities": ENTITY_COUNT, "filler": FILLER_PATHS})
    # Filled by the seed's inserts, the GiST index differs in size between runs by tens of pages, which changes
    # the planner's cost estimates. Rebuilt, it still differs by a few pages, but no longer enough to change them.
    db.session.execute(text("REINDEX INDEX ix_flat_path_gist"))
    # Without fresh statistics the planner guesses at row counts and the plan shape is arbitrary. ANALYZE samples
    # 300 * default_statistics_target rows (30,000 by default); the seed stays below that, so it reads every row
    # and the statistics are the same on every run.
    db.session.execute(text("ANALYZE ai_search_index"))
    for name, value in PLAN_SETTINGS.items():
        db.session.execute(text("SELECT set_config(:name, :value, true)"), {"name": name, "value": value})
    # Counts calls to non-builtin functions, such as ltree's, for the plan metrics. Only a superuser may set it.
    db.session.execute(text("SELECT set_config('track_functions', 'all', true)"))


def _matching(matches):
    return [n for n in range(1, ENTITY_COUNT + 1) if matches(n)]


@contextmanager
def _capturing_plans():
    """Run EXPLAIN ANALYZE next to every SELECT, with the statement's own compiled SQL and bound parameters.

    The plan is read from the raw cursor: through SQLAlchemy, the statement's result processors would
    be applied to the EXPLAIN output. Each plan also gets the number of function calls the statement made.
    """
    conn = db.session.connection()
    plans = []

    def function_calls(cursor):
        # Counted per transaction, not per statement: a statement's calls are the difference around it.
        cursor.execute("SELECT coalesce(sum(calls), 0)::bigint FROM pg_stat_xact_user_functions")
        return cursor.fetchone()[0]

    def explain(_conn, cursor, statement, parameters, _context, _executemany):
        # Session bookkeeping (SAVEPOINT, SET) cannot be explained and has no plan worth bounding.
        if statement.lstrip().upper().startswith("SELECT"):
            calls_before = function_calls(cursor)
            cursor.execute(f"EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, FORMAT JSON) {statement}", parameters)
            plan = cursor.fetchone()[0][0]["Plan"]
            plans.append(plan | {"Function Calls": function_calls(cursor) - calls_before})

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


def _blocks(node):
    # Hits and reads together: which of the two a block is depends on the cache, their sum does not.
    return node["Shared Hit Blocks"] + node["Shared Read Blocks"]


def _own_blocks(node):
    return _blocks(node) - sum(map(_blocks, node.get("Plans", [])))


# Like Actual Rows, these are averages per loop.
ROWS_REMOVED_KEYS = ("Rows Removed by Filter", "Rows Removed by Join Filter", "Rows Removed by Index Recheck")


def _plan_metrics(plan):
    """What one statement cost Postgres, as numbers that are the same on every run.

    - ``cost``: the planner's estimated total cost of the statement, decided before it runs. Its unit is one
      sequential page read; random page reads, rows and operator calls are weighted in by the ``*_cost`` settings.
      It follows from the plan and the statistics only, so it changes with the plan, not with how the plan ran.
    - ``blocks``: 8kB pages the statement read, from shared buffers or from disk. Measured. Leaves out those of the
      GiST index: even rebuilt, how its pages split varies a little between runs.
    - ``rows``: rows output by all nodes together, over all their loops. Measured. Counts the work between the nodes,
      so a filter moved to a node that runs more often shows even when the result is the same.
    - ``max_loops``: how often the busiest node ran. Measured. A node running once per index row instead of once per
      entity shows here first.
    - ``filtered``: rows nodes read and then discarded, by a filter, a join filter or an index recheck, over all their
      loops. Measured. Work that did not contribute to the result, so the same result found more selectively shows.
    - ``function_calls``: calls to non-builtin functions, such as ltree's ``ltq_regex`` behind ``path ~ lquery``,
      made while evaluating a filter. Measured. Calls an index makes while searching itself are not counted, so this
      is the CPU work of matching patterns row by row that ``rows`` does not show, and stays 0 while every pattern is
      an index condition.
    """
    nodes = list(_plan_nodes(plan))
    gist_blocks = sum(_own_blocks(node) for node in nodes if node.get("Index Name") == "ix_flat_path_gist")
    return {
        "cost": plan["Total Cost"],
        "blocks": _blocks(plan) - gist_blocks,
        "rows": sum(node["Actual Rows"] * node["Actual Loops"] for node in nodes),
        "max_loops": max(node["Actual Loops"] for node in nodes),
        "filtered": sum(node.get(removed, 0) * node["Actual Loops"] for node in nodes for removed in ROWS_REMOVED_KEYS),
        "function_calls": plan["Function Calls"],
    }


def _postgres_major():
    return db.session.connection().dialect.server_version_info[0]


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


def _select_stmt(query):
    return Retriever.route(query, cursor=None).apply(build_candidate_query(query)).limit(query.limit)


def _count_stmt(filters):
    query = CountQuery(entity_type=EntityType.SUBSCRIPTION, filters=FilterTree.model_validate(filters))
    return build_simple_count_query(build_candidate_query(query))


def _search_page(async_session, page):
    """The query and cursor to search `page`, with half of the matches per page."""
    total = len(_matching(_matches_status_and_speed_or_customer))
    # Page 2 exists as long as the filter matches at least two entities.
    query = _select_query(STATUS_AND_SPEED_OR_CUSTOMER, limit=min(SelectQuery.MAX_LIMIT, max(1, total // 2)))
    if page == 1:
        return query, None
    last = asyncio.run(execute_search(query, async_session)).results[-1]
    return query, PageCursor(score=last.score, id=last.entity_id, query_id=uuid4(), order_value=last.order_value)


@pytest.mark.parametrize("filters,matches", FILTER_SHAPES)
def test_select_runs_each_plan_node_at_most_once_per_entity(seeded_index, benchmark, filters, matches):
    query = _select_query(filters)
    stmt = _select_stmt(query)
    conn = db.session.connection()

    @benchmark
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
def test_count_runs_each_plan_node_at_most_once_per_entity(seeded_index, benchmark):
    """The count query wraps the candidate query."""
    stmt = _count_stmt(STATUS_AND_SPEED_OR_CUSTOMER)
    conn = db.session.connection()

    @benchmark
    def total_count():
        return conn.execute(stmt).scalar_one()

    assert total_count == len(_matching(_matches_status_and_speed_or_customer))
    # Counting a column of the inner query instead of its subquery would make SQLAlchemy emit both: a cartesian product.
    assert len(stmt.get_final_froms()) == 1
    _assert_no_node_runs_per_index_row(_plan(stmt))


@pytest.mark.xfail(strict=True, reason="EXISTS under OR inside AND is re-run per index row")
@pytest.mark.parametrize("page", [pytest.param(1, id="page_1"), pytest.param(2, id="page_2")])
def test_search_total_count_runs_each_plan_node_at_most_once_per_entity(seeded_index, async_session, benchmark, page):
    """The search endpoint counts all matches, and from page 2 on also the matches from the cursor on."""
    query, cursor = _search_page(async_session, page)

    @benchmark
    def response():
        return asyncio.run(execute_search(query, async_session, cursor=cursor))

    assert response.total_items == len(_matching(_matches_status_and_speed_or_customer))
    assert response.start_cursor == (page - 1) * query.limit

    with _capturing_plans() as plans:
        asyncio.run(execute_search(query, async_session, cursor=cursor))
    for plan in plans:
        _assert_no_node_runs_per_index_row(plan)


def _select_plans(filters, _async_session):
    return [_plan(_select_stmt(_select_query(filters)))]


def _count_plans(filters, _async_session):
    return [_plan(_count_stmt(filters))]


def _search_plans(page, async_session):
    query, cursor = _search_page(async_session, page)
    with _capturing_plans() as plans:
        asyncio.run(execute_search(query, async_session, cursor=cursor))
    return plans


# Without the xfail marks of FILTER_SHAPES: inline-snapshot ignores snapshots in xfail tests.
PLAN_SCENARIOS = [
    *(pytest.param(partial(_select_plans, shape.values[0]), id=f"select-{shape.id}") for shape in FILTER_SHAPES),
    pytest.param(partial(_count_plans, STATUS_AND_SPEED_OR_CUSTOMER), id="count"),
    *(pytest.param(partial(_search_plans, page), id=f"search-page_{page}") for page in (1, 2)),
]


@pytest.mark.parametrize("plans", PLAN_SCENARIOS)
def test_plan_cost_is_unchanged(seeded_index, async_session, plans, request):
    """Each statement's cost, in execution order: a search runs its select, then one count per page boundary.

    Plans differ between Postgres major versions, so each has its own snapshot.
    """
    metrics = [_plan_metrics(plan) for plan in plans(async_session)]
    assert (
        metrics
        == snapshot(
            {
                "select-status_and_customer": {
                    17: [
                        {
                            "cost": 686.68,
                            "blocks": 3370,
                            "rows": 3984,
                            "max_loops": 900,
                            "filtered": 1000,
                            "function_calls": 0,
                        }
                    ],
                    15: [
                        {
                            "cost": 686.69,
                            "blocks": 3370,
                            "rows": 3984,
                            "max_loops": 900,
                            "filtered": 1000,
                            "function_calls": 0,
                        }
                    ],
                },
                "select-speed_or_customer": {
                    17: [
                        {
                            "cost": 2283547.97,
                            "blocks": 22412,
                            "rows": 26006,
                            "max_loops": 260,
                            "filtered": 19745,
                            "function_calls": 0,
                        }
                    ],
                    15: [
                        {
                            "cost": 2282646.56,
                            "blocks": 1459,
                            "rows": 26006,
                            "max_loops": 260,
                            "filtered": 19745,
                            "function_calls": 0,
                        }
                    ],
                },
                "select-status_and_nested_speed_or_customer": {
                    17: [
                        {
                            "cost": 13982.29,
                            "blocks": 69526,
                            "rows": 33206,
                            "max_loops": 15816,
                            "filtered": 31976,
                            "function_calls": 0,
                        }
                    ],
                    15: [
                        {
                            "cost": 13983.2,
                            "blocks": 69526,
                            "rows": 33206,
                            "max_loops": 15816,
                            "filtered": 31976,
                            "function_calls": 0,
                        }
                    ],
                },
                "select-nested_status_and_speed_or_customer": {
                    17: [
                        {
                            "cost": 2485944.96,
                            "blocks": 22523,
                            "rows": 27926,
                            "max_loops": 260,
                            "filtered": 19845,
                            "function_calls": 0,
                        }
                    ],
                    15: [
                        {
                            "cost": 2484922.4,
                            "blocks": 1570,
                            "rows": 27926,
                            "max_loops": 260,
                            "filtered": 19845,
                            "function_calls": 0,
                        }
                    ],
                },
                "select-no_node": {
                    17: [
                        {
                            "cost": 22013.32,
                            "blocks": 2472,
                            "rows": 67361,
                            "max_loops": 667,
                            "filtered": 0,
                            "function_calls": 0,
                        }
                    ],
                    15: [
                        {
                            "cost": 22113.64,
                            "blocks": 2472,
                            "rows": 43361,
                            "max_loops": 667,
                            "filtered": 0,
                            "function_calls": 0,
                        }
                    ],
                },
                "select-status_and_no_node": {
                    17: [
                        {
                            "cost": 1882.17,
                            "blocks": 535479,
                            "rows": 97650,
                            "max_loops": 21900,
                            "filtered": 525700,
                            "function_calls": 533100,
                        }
                    ],
                    15: [
                        {
                            "cost": 1882.98,
                            "blocks": 535479,
                            "rows": 97650,
                            "max_loops": 21900,
                            "filtered": 525700,
                            "function_calls": 533100,
                        }
                    ],
                },
                "select-customer_or_no_node": {
                    17: [
                        {
                            "cost": 1090081.37,
                            "blocks": 23558,
                            "rows": 36114,
                            "max_loops": 674,
                            "filtered": 9140,
                            "function_calls": 0,
                        }
                    ],
                    15: [
                        {
                            "cost": 1089179.97,
                            "blocks": 2605,
                            "rows": 36114,
                            "max_loops": 674,
                            "filtered": 9140,
                            "function_calls": 0,
                        }
                    ],
                },
                "count": {
                    17: [
                        {
                            "cost": 24384.04,
                            "blocks": 137312,
                            "rows": 180193,
                            "max_loops": 15816,
                            "filtered": 63932,
                            "function_calls": 0,
                        }
                    ],
                    15: [
                        {
                            "cost": 24384.04,
                            "blocks": 137312,
                            "rows": 180193,
                            "max_loops": 15816,
                            "filtered": 63932,
                            "function_calls": 0,
                        }
                    ],
                },
                "search-page_1": {
                    17: [
                        {
                            "cost": 22856.47,
                            "blocks": 70345,
                            "rows": 127118,
                            "max_loops": 15816,
                            "filtered": 32067,
                            "function_calls": 0,
                        },
                        {
                            "cost": 12890.11,
                            "blocks": 69436,
                            "rows": 23147,
                            "max_loops": 15816,
                            "filtered": 31966,
                            "function_calls": 0,
                        },
                    ],
                    15: [
                        {
                            "cost": 22857.38,
                            "blocks": 70345,
                            "rows": 127118,
                            "max_loops": 15816,
                            "filtered": 32067,
                            "function_calls": 0,
                        },
                        {
                            "cost": 12890.11,
                            "blocks": 69436,
                            "rows": 23147,
                            "max_loops": 15816,
                            "filtered": 31966,
                            "function_calls": 0,
                        },
                    ],
                },
                "search-page_2": {
                    17: [
                        {
                            "cost": 17296.65,
                            "blocks": 71125,
                            "rows": 127278,
                            "max_loops": 15816,
                            "filtered": 32167,
                            "function_calls": 0,
                        },
                        {
                            "cost": 12890.11,
                            "blocks": 69436,
                            "rows": 23147,
                            "max_loops": 15816,
                            "filtered": 31966,
                            "function_calls": 0,
                        },
                        {
                            "cost": 13901.22,
                            "blocks": 70216,
                            "rows": 23207,
                            "max_loops": 15816,
                            "filtered": 32066,
                            "function_calls": 0,
                        },
                    ],
                    15: [
                        {
                            "cost": 17296.65,
                            "blocks": 71125,
                            "rows": 127278,
                            "max_loops": 15816,
                            "filtered": 32167,
                            "function_calls": 0,
                        },
                        {
                            "cost": 12890.11,
                            "blocks": 69436,
                            "rows": 23147,
                            "max_loops": 15816,
                            "filtered": 31966,
                            "function_calls": 0,
                        },
                        {
                            "cost": 13901.22,
                            "blocks": 70216,
                            "rows": 23207,
                            "max_loops": 15816,
                            "filtered": 32066,
                            "function_calls": 0,
                        },
                    ],
                },
            }
        )[request.node.callspec.id][_postgres_major()]
    )
