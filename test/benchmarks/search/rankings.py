# Copyright 2019-2026 ESnet, GÉANT, SURF.
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

"""The top results of every query as one markdown page, with drift from a baseline page marked. Pure functions."""

import re
from collections.abc import Mapping, Sequence

from test.benchmarks.search.metrics import Hit, QueryResult

RANKING_CUTOFF = 10
DRIFT = "⚠ drift"
NEW_QUERY = "new query"
# Longer matched values are cut here, so one entity with a long description does not hide the rest of the table.
CELL_LENGTH = 80

# A query's heading and its table rows, as `render_rankings` writes them.
_HEADING = re.compile(r"^### (\S+) · query: `(.+?)`")
_ROW = re.compile(r"^\| (\d+) \| (\S+) \|")

QueryId = tuple[str, str]


def query_id(result: QueryResult) -> QueryId:
    """The category and text of a query. Text alone is not unique: the same text can be in two categories."""
    return result.query.category.value, result.query.text


def read_rankings(markdown: str) -> dict[QueryId, tuple[str, ...]]:
    """The top results per query of a page written by `render_rankings`, best first."""
    rankings: dict[QueryId, tuple[str, ...]] = {}
    current: QueryId | None = None
    for line in markdown.splitlines():
        if heading := _HEADING.match(line):
            current = (heading.group(1), heading.group(2))
            rankings[current] = ()
        elif current is not None and (row := _ROW.match(line)):
            rankings[current] += (row.group(2),)
    return rankings


def _change(result: QueryResult, baseline: Mapping[QueryId, Sequence[str]] | None) -> str:
    """Whether the top results of `result` drifted from the baseline: "" when unchanged or there is no baseline."""
    if baseline is None:
        return ""
    previous = baseline.get(query_id(result))
    if previous is None:
        return NEW_QUERY
    return DRIFT if tuple(previous) != tuple(result.ranked[:RANKING_CUTOFF]) else ""


def _cell(text: str) -> str:
    """Text fit for a markdown table cell: one line, no pipes, shortened to `CELL_LENGTH`."""
    flat = " ".join(text.split()).replace("|", "\\|")
    return flat if len(flat) <= CELL_LENGTH else flat[: CELL_LENGTH - 1] + "…"


def _rows(result: QueryResult, previous: Sequence[str] | None) -> list[str]:
    """One table row per returned entity in the top results, with where it came from in the baseline."""
    expected = set(result.query.expected)
    previous_rank = {key: rank for rank, key in enumerate(previous or (), start=1)}
    hits = result.hits or tuple(Hit(key) for key in result.ranked)

    def note(rank: int, key: str) -> str:
        if previous is None:
            return ""
        if key not in previous_rank:
            return "new"
        return "" if previous_rank[key] == rank else f"was #{previous_rank[key]}"

    return [
        f"| {rank} | {hit.key} | {_cell(hit.title)} | {_cell(hit.matched_path)} | {_cell(hit.matched_text)} "
        f"| {'✓' if hit.key in expected else ''} | {note(rank, hit.key)} |"
        for rank, hit in enumerate(hits[:RANKING_CUTOFF], start=1)
    ]


def _section(result: QueryResult, baseline: Mapping[QueryId, Sequence[str]] | None) -> str:
    previous = None if baseline is None else baseline.get(query_id(result))
    change = _change(result, baseline)
    heading = f"### {result.query.category.value} · query: `{result.query.text}`" + (f" — {change}" if change else "")
    top = tuple(result.ranked[:RANKING_CUTOFF])
    dropped = [key for key in previous or () if key not in top]
    lines = [
        heading,
        "",
        "| # | entity | title | matched path | matched value | expected | vs baseline |",
        "|---:|---|---|---|---|:---:|---|",
        *_rows(result, previous),
    ]
    if dropped:
        lines += ["", f"Dropped from the top {RANKING_CUTOFF}: " + ", ".join(f"`{key}`" for key in dropped)]
    return "\n".join(lines)


def render_rankings(
    title: str,
    description: str,
    results: Sequence[QueryResult],
    baseline: Mapping[QueryId, Sequence[str]] | None,
) -> str:
    """A markdown page with the top results of every query, query first, marked where it drifted from `baseline`.

    `baseline` is the top results per query of an earlier page (see `read_rankings`); None when there is none yet, in
    which case nothing is marked.
    """
    changes = [_change(result, baseline) for result in results]
    if baseline is None:
        summary = "No baseline yet: nothing to compare against."
    else:
        summary = (
            f"{len(results)} queries: {changes.count(DRIFT)} drifted from the baseline, {changes.count(NEW_QUERY)} new."
        )
    sections = "\n\n".join(_section(result, baseline) for result in results)
    return f"""# {title}

{description}

Generated by the search benchmark into `report/`, not committed. Compared against `baseline/rankings.pg<major>.md`: to
accept these results as the new baseline, copy the page there and commit it.

{summary}

The top {RANKING_CUTOFF} results per query, best first. ✓ marks an expected entity. "was #n" is the rank in the
baseline, "new" an entity that was not in the baseline's top {RANKING_CUTOFF}.

{sections}
"""
