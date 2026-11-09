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

"""The top results of every query as one markdown page: what the accuracy table does not show, the why. Pure functions.

The page opens with a summary of every query, misses first, each linking to its section. A section gives the query's
verdict, what it expects and the top results with their scores, so ties and near-misses are visible.
"""

from collections.abc import Sequence

from test.benchmarks.search.metrics import Hit, QueryResult, first_rank, found_at

RANKING_CUTOFF = 10
# Longer matched values are cut here, so one entity with a long description does not hide the rest of the table.
CELL_LENGTH = 80
# Expected entities named in a section. A `customer_typo` query expects hundreds.
SHOWN_EXPECTED = 10

PASSED, MISSED = "✓", "✗"


def _cell(text: str) -> str:
    """Text fit for a markdown table cell: one line, no pipes, shortened to `CELL_LENGTH`."""
    flat = " ".join(text.split()).replace("|", "\\|")
    return flat if len(flat) <= CELL_LENGTH else flat[: CELL_LENGTH - 1] + "…"


def _keys(keys: Sequence[str]) -> str:
    """The first `SHOWN_EXPECTED` keys, and how many more there are."""
    shown = ", ".join(keys[:SHOWN_EXPECTED])
    return f"{shown}, … {len(keys) - SHOWN_EXPECTED} more" if len(keys) > SHOWN_EXPECTED else shown


def _anchor(index: int) -> str:
    return f"q{index}"


def passed(result: QueryResult) -> bool:
    """A query with right answers passes with one on top, a negative query when it returns nothing."""
    expected = result.query.expected
    return first_rank(result.ranked, expected) == 1 if expected else not result.ranked


def _first_right(result: QueryResult) -> str:
    rank = first_rank(result.ranked, result.query.expected)
    return f"rank {rank}" if rank else "not returned"


def _in_top(result: QueryResult) -> str:
    """How many right answers made the top, of how many could."""
    expected = result.query.expected
    return f"{len(found_at(result.ranked, expected, RANKING_CUTOFF))} of {min(len(expected), RANKING_CUTOFF)}"


def _outcome(result: QueryResult) -> tuple[str, str]:
    """The first right answer and the right answers in the top, or for a negative query how much it returned."""
    if result.query.expected:
        return _first_right(result), _in_top(result)
    return f"{len(result.ranked)} returned" if result.ranked else "nothing returned", "—"


def _summary(results: Sequence[QueryResult]) -> str:
    """One row per query, misses first, in benchmark order within each."""
    indexed = sorted(enumerate(results), key=lambda item: passed(item[1]))
    rows = [
        f"| {PASSED if passed(result) else MISSED} | {result.query.category.value} "
        f"| [`{_cell(result.query.text)}`](#{_anchor(index)}) | {' | '.join(_outcome(result))} |"
        for index, result in indexed
    ]
    return "\n".join(
        [
            f"| | category | query | first right answer | right answers in top {RANKING_CUTOFF} |",
            "|:---:|---|---|---|---|",
            *rows,
        ]
    )


def _verdict(result: QueryResult) -> str:
    """What the query expects and how it did, in words."""
    expected = result.query.expected
    if not expected:
        return "Expects nothing: any result is a false positive."
    first, in_top = _outcome(result)
    lines = [
        f"Expects {len(expected)}: {_keys(expected)}.",
        f"First right answer: {first}. Right answers in top {RANKING_CUTOFF}: {in_top}.",
    ]
    # With more right answers than fit, missing ones are expected and too many to list.
    missing = [key for key in expected if key not in found_at(result.ranked, expected, RANKING_CUTOFF)]
    if missing and len(expected) <= RANKING_CUTOFF:
        lines.append(f"Missing from top {RANKING_CUTOFF}: {_keys(missing)}.")
    return "  \n".join(lines)


def _score(hit: Hit) -> str:
    return "" if hit.score is None else f"{hit.score:.3f}"


def _results(result: QueryResult) -> str:
    if not result.ranked:
        return "No results."
    expected = set(result.query.expected)
    hits = result.hits or tuple(Hit(key) for key in result.ranked)
    rows = [
        f"| {rank} | {_score(hit)} | {hit.key} | {PASSED if hit.key in expected else ''} | {_cell(hit.title)} "
        f"| {_cell(hit.matched_path)} | {_cell(hit.matched_text)} |"
        for rank, hit in enumerate(hits[:RANKING_CUTOFF], start=1)
    ]
    return "\n".join(
        [
            "| # | score | entity | right answer | title | matched path | matched value |",
            "|---:|---:|---|:---:|---|---|---|",
            *rows,
        ]
    )


def _section(index: int, result: QueryResult) -> str:
    query = result.query
    note = [f"> {query.note}", ""] if query.note else []
    return "\n".join(
        [
            f'<a id="{_anchor(index)}"></a>',
            "",
            f"### {PASSED if passed(result) else MISSED} {query.category.value} · `{query.text}`",
            "",
            _verdict(result),
            "",
            *note,
            _results(result),
        ]
    )


def render_rankings(title: str, description: str, results: Sequence[QueryResult]) -> str:
    """A markdown page with a summary of every query, then its top results, query first."""
    sections = "\n\n".join(_section(index, result) for index, result in enumerate(results))
    missed = sum(not passed(result) for result in results)
    return f"""# {title}

{description}

Generated by the search benchmark into `report/`, not committed. Compare two runs with a diff of their pages.

A query passes ({PASSED}) when a right answer ranks first, or, for a `negative` query, when nothing is returned. A
*right answer* is an entity in the query's label (`expected`): any entity the query should find, so a query can have
several. A right answer below rank 1 is fine when rank 1 is one too, and a miss when a wrong entity ranks above it.
`score` is the retriever's score. Equal scores are ties, which search orders by entity id: a stable order, but not a
ranking.

## Summary

{missed} of {len(results)} queries missed.

{_summary(results)}

## Queries

The top {RANKING_CUTOFF} results per query, best first.

{sections}
"""
