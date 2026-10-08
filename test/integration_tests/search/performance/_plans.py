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

"""What search statements cost Postgres, as numbers that are the same on every run.

CodSpeed's simulation counts only this process's instructions, not the work inside Postgres, and wall-clock time is
too noisy to compare. The work Postgres does is deterministic, though: with the same data, statistics and settings,
``EXPLAIN (ANALYZE, BUFFERS)`` reports the same plan, blocks and rows on every run. A test module seeds the index with
`seed_index`, captures the plans of its scenarios with `capturing_plans`, and compares their `plan_metrics`, rendered
by `render_plan_metrics`, to its snapshot with `assert_plan_metrics_unchanged`: a markdown file under ``plan_metrics/``
per Postgres major version. Update those with ``pytest --inline-snapshot=fix``.
"""

import difflib
from contextlib import contextmanager
from pathlib import Path

import pytest
from inline_snapshot import external_file
from more_itertools import one, unique_everseen
from sqlalchemy import event, text

from orchestrator.core.db import db

# ANALYZE samples 300 * default_statistics_target rows. A seed below that is read whole, so the statistics are the same
# on every run.
MAX_SEED_ROWS = 300 * 100

# Settings the plans depend on that could differ per server or run: parallel workers split the work unpredictably and
# JIT kicks in on cost thresholds. work_mem decides between in-memory and on-disk sorts.
PLAN_SETTINGS = {
    "max_parallel_workers_per_gather": "0",
    "jit": "off",
    "work_mem": "4MB",
    # Counts calls to non-builtin functions, such as ltree's, for `function_calls`. Only a superuser may set it.
    "track_functions": "all",
}

# Filled by the seed's inserts, this index differs in size between runs by tens of pages, which changes the planner's
# cost estimates. Rebuilt, it still differs by a few pages, no longer enough to change them, but its blocks read do.
GIST_INDEX = "ix_flat_path_gist"
TRIGRAM_INDEX = "ix_flat_value_trgm"

# Like Actual Rows, these are averages per loop.
ROWS_REMOVED_KEYS = ("Rows Removed by Filter", "Rows Removed by Join Filter", "Rows Removed by Index Recheck")

# The metrics `plan_metrics` reports, with the legend `render_plan_metrics` gives them.
METRICS = {
    "cost": "the planner's estimated total cost of the statement, decided before it runs. Its unit is one sequential "
    "page read; random page reads, rows and operator calls are weighted in by the `*_cost` settings. It follows from "
    "the plan and the statistics only, so it changes with the plan, not with how the plan ran.",
    "blocks": "8kB pages the statement read, from shared buffers or from disk. Measured. Leaves out those of the GiST "
    "path index: even rebuilt after seeding, its size varies a little between runs.",
    "rows": "rows output by all plan nodes together, over all their loops. Measured. Counts the work between the nodes, "
    "so a filter moved to a node that runs more often shows even when the result is the same.",
    "max_loops": "how often the busiest plan node ran. Measured. A node running once per index row instead of once per "
    "entity shows here first.",
    "filtered": "rows plan nodes read and then discarded, by a filter, a join filter or an index recheck, over all "
    "their loops. Measured. Work that did not contribute to the result, so the same result found more selectively "
    "shows.",
    "function_calls": "calls to non-builtin functions, such as ltree's `ltq_regex` behind `path ~ lquery` or pg_trgm's "
    "similarity functions, made while evaluating a condition row by row. Measured. Calls an index makes while "
    "searching itself are not counted, so this is CPU work that `rows` does not show, and stays 0 while every "
    "pattern is an index condition.",
}


def seed_index(seed_sql, **params):
    """Fill ai_search_index with `seed_sql` only, so that its plans are the same on every run."""
    # Rows of earlier tests are rolled back but stay on their pages until vacuumed, which would change the blocks read.
    # TRUNCATE gives the seed fresh files, and like ALTER TABLE it is transactional: the per-test rollback restores the
    # table and re-enables the trigger.
    db.session.execute(text("TRUNCATE ai_search_index"))
    # The trigger maintains ai_search_paths, which these tests never read; bypassing it halves the seed time.
    db.session.execute(text("ALTER TABLE ai_search_index DISABLE TRIGGER ai_search_paths_maintain_trg"))
    rows = db.session.execute(seed_sql, params).rowcount
    assert rows <= MAX_SEED_ROWS, f"ANALYZE would sample {MAX_SEED_ROWS} of the {rows} seeded rows"
    db.session.execute(text(f"REINDEX INDEX {GIST_INDEX}"))
    # Inserted rows wait in the GIN index's pending list until something flushes it, and how much has been flushed by
    # then varies between runs. Rebuilt, it has none.
    db.session.execute(text(f"REINDEX INDEX {TRIGRAM_INDEX}"))
    # Without fresh statistics the planner guesses at row counts and the plan shape is arbitrary.
    db.session.execute(text("ANALYZE ai_search_index"))
    for name, value in PLAN_SETTINGS.items():
        db.session.execute(text("SELECT set_config(:name, :value, true)"), {"name": name, "value": value})


@contextmanager
def capturing_plans():
    """Run EXPLAIN ANALYZE next to every SELECT, with the statement's own compiled SQL and bound parameters.

    The plan is read from the raw cursor: through SQLAlchemy, the statement's result processors would be applied to
    the EXPLAIN output. Each plan also gets the number of function calls the statement made.
    """
    conn = db.session.connection()
    plans = []

    def function_calls(cursor):
        # Counted per transaction, not per statement: a statement's calls are the difference around it.
        cursor.execute("SELECT coalesce(sum(calls), 0)::bigint FROM pg_stat_xact_user_functions")
        return cursor.fetchone()[0]

    def explain(_conn, cursor, statement, parameters, _context, _executemany):
        # Session bookkeeping (SAVEPOINT, SET) cannot be explained and has no plan worth measuring.
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


def plan_of(stmt):
    """The plan of `stmt`, from an execution of its own so it never adds to a benchmark."""
    with capturing_plans() as plans:
        db.session.connection().execute(stmt).all()
    return one(plans)


def plan_nodes(node):
    yield node
    for child in node.get("Plans", []):
        yield from plan_nodes(child)


def assert_no_node_runs_more_often_than(plan, bound, unit):
    busiest = max(plan_nodes(plan), key=lambda node: node["Actual Loops"])
    name = " ".join(filter(None, [busiest["Node Type"], busiest.get("Subplan Name"), busiest.get("Relation Name")]))
    assert busiest["Actual Loops"] <= bound, f"{name} ran {busiest['Actual Loops']} times for {bound} {unit}"


def _blocks(node):
    # Hits and reads together: which of the two a block is depends on the cache, their sum does not.
    return node["Shared Hit Blocks"] + node["Shared Read Blocks"]


def _own_blocks(node):
    return _blocks(node) - sum(map(_blocks, node.get("Plans", [])))


def plan_metrics(plan):
    """What one statement cost Postgres, as the `METRICS`."""
    nodes = list(plan_nodes(plan))
    gist_blocks = sum(_own_blocks(node) for node in nodes if node.get("Index Name") == GIST_INDEX)
    return {
        "cost": plan["Total Cost"],
        "blocks": _blocks(plan) - gist_blocks,
        "rows": sum(node["Actual Rows"] * node["Actual Loops"] for node in nodes),
        "max_loops": max(node["Actual Loops"] for node in nodes),
        "filtered": sum(node.get(removed, 0) * node["Actual Loops"] for node in nodes for removed in ROWS_REMOVED_KEYS),
        "function_calls": plan["Function Calls"],
    }


def postgres_major():
    return db.session.connection().dialect.server_version_info[0]


def _format(value):
    return f"{value:,.2f}" if isinstance(value, float) else f"{value:,}"


def _table(header, rows):
    """A markdown table that also lines up as plain text: the first column left-aligned, the others right-aligned."""
    # At least 3 wide: a delimiter cell needs a hyphen besides the colon.
    widths = [max(3, *map(len, column)) for column in zip(header, *rows)]

    def line(cells):
        aligned = [
            cell.ljust(width) if i == 0 else cell.rjust(width) for i, (cell, width) in enumerate(zip(cells, widths))
        ]
        return f"| {' | '.join(aligned)} |"

    separator = ["-" * widths[0], *("-" * (width - 1) + ":" for width in widths[1:])]
    return "\n".join([line(header), line(separator), *map(line, rows)])


def render_plan_metrics(title, description, scenarios):
    """A markdown page of the `plan_metrics` of each scenario's statements, with a legend.

    Args:
        title: The page title.
        description: What the scenarios measure, on which data.
        scenarios: For each scenario, the metrics of each statement it ran, in execution order.
    """
    rows = [
        [scenario, str(position), *(_format(metrics[name]) for name in METRICS)]
        for scenario, statements in scenarios.items()
        for position, metrics in enumerate(statements, start=1)
    ]
    legend = "\n".join(f"- `{name}`: {meaning}" for name, meaning in METRICS.items())
    return f"""# {title} on Postgres {postgres_major()}

{description}

Generated by the plan metrics test next to this directory. Update with `pytest --inline-snapshot=fix`.

{_table(["scenario", "#", *METRICS], rows)}

## Legend

Each row is one statement a scenario ran, `#` its position in execution order.

{legend}
"""


def _table_lines(page):
    return [line for line in page.splitlines() if line.startswith("|")]


def _statements(page):
    """The cells of a rendered table per statement, keyed by its scenario and position."""
    if not (lines := _table_lines(page)):
        return {}
    header, _separator, *rows = ([cell.strip() for cell in line.strip("|").split("|")] for line in lines)
    return {(scenario, position): dict(zip(header[2:], cells)) for scenario, position, *cells in rows}


MISSING = "—"


def _relative_change(stored, measured):
    if MISSING in (stored, measured):
        return ""
    old, new = (float(value.replace(",", "")) for value in (stored, measured))
    if old == 0:
        return "from 0"
    change = (new - old) / old
    # Costs move by fractions of a percent, which would round to a misleading 0.0%.
    return f"{change:+.1%}" if round(change, 3) else f"{'+' if change > 0 else '-'}<0.1%"


def _metric_changes(stored_page, measured_page):
    """Each statement whose metrics differ, with the metrics that do; statements can be added or removed too."""
    stored, measured = _statements(stored_page), _statements(measured_page)
    for key in unique_everseen([*measured, *stored]):
        old, new = stored.get(key, {}), measured.get(key, {})
        changes = [
            (name, old.get(name, MISSING), new.get(name, MISSING))
            for name in unique_everseen([*new, *old])
            if old.get(name) != new.get(name)
        ]
        if changes:
            status = " (added)" if not old else " (removed)" if not new else ""
            yield f"{key[0]} #{key[1]}{status}", changes


def _render_changes(stored_page, measured_page):
    statements = list(_metric_changes(stored_page, measured_page))
    if not statements:
        diff = difflib.unified_diff(stored_page.splitlines(), measured_page.splitlines(), lineterm="", n=0)
        return "No metric changed, the text around the table did:\n\n" + "\n".join(list(diff)[2:])
    cells = [change for _, changes in statements for change in changes]
    widths = [max(map(len, column)) for column in zip(*cells)]

    def line(name, old, new):
        change = _relative_change(old, new)
        return f"    {name:<{widths[0]}}  {old:>{widths[1]}} → {new:>{widths[2]}}  {change:>7}".rstrip()

    return "\n".join(
        f"  {statement}\n" + "\n".join(line(*change) for change in changes) for statement, changes in statements
    )


def assert_plan_metrics_unchanged(name, page):
    """Compare `page` to `name`'s snapshot on this server; plans differ between Postgres major versions.

    On a change, the failure shows the measured table and then only the metrics that moved, as pytest's diff of the
    whole page does not show which cells differ.
    """
    path = Path(__file__).parent / "plan_metrics" / f"{name}.pg{postgres_major()}.md"
    if page == external_file(path, format=".txt"):
        return
    stored = path.read_text() if path.exists() else ""
    measured_table = "\n".join(_table_lines(page))
    pytest.fail(
        f"Plan metrics differ from {path.name}. Update it with `pytest --inline-snapshot=fix` if that is expected.\n\n"
        f"Measured:\n\n{measured_table}\n\nChanged (stored → measured):\n\n{_render_changes(stored, page)}",
        pytrace=False,
    )
