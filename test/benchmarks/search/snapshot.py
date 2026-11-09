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

"""The corpus and the generated queries as markdown pages, committed so that a change to either shows in a diff.

Columns line up so the pages read as plain text, at fixed widths rather than the widest value: a width taken from the
data would change with one long value and re-pad every line, while a fixed one changes only the row of the entity or
query that changed. A value wider than its column pushes the rest of its own row out of line. Pure functions.
"""

from collections.abc import Iterable, Sequence
from typing import NamedTuple

from test.benchmarks.search.corpus import CUSTOMER, DESCRIPTION, IDENTIFIER, LOCATION, Corpus
from test.benchmarks.search.perturb import LabelledQuery

# Expected keys shown per query. A `customer_typo` query expects every service of the customer, hundreds of them.
SHOWN_EXPECTED = 10

UPDATE = "Update with `pytest test/unit_tests/benchmarks/search --inline-snapshot=fix`."


def _cell(values: Iterable[str]) -> str:
    """Distinct `values` in order, as one markdown table cell."""
    return ", ".join(dict.fromkeys(values)).replace("|", "\\|")


class Column(NamedTuple):
    """A table column: its header, the width it is padded to, and whether it is right-aligned, as numbers are."""

    name: str
    width: int = 0
    right: bool = False

    def pad(self, cell: str) -> str:
        return cell.rjust(self.width) if self.right else cell.ljust(self.width)

    @property
    def separator(self) -> str:
        width = max(3, self.width)
        return "-" * (width - 1) + ":" if self.right else "-" * width


def _row(columns: Sequence[Column], cells: Sequence[str]) -> str:
    return f"| {' | '.join(column.pad(cell) for column, cell in zip(columns, cells, strict=True))} |"


def _table(columns: Sequence[Column], rows: Iterable[Sequence[str]]) -> str:
    """A markdown table padded to the widths of `columns`. Give the last column no width: it has nothing to line up."""
    header = [column.name for column in columns]
    separator = [column.separator for column in columns]
    return "\n".join(_row(columns, cells) for cells in (header, separator, *rows))


# Widths fit the network services profile, with a little room. Another profile with longer values still renders, with
# those rows out of line.
CORPUS_COLUMNS = (
    Column("key", 20),
    Column(DESCRIPTION, 46),
    Column(IDENTIFIER, 54),
    Column(CUSTOMER, 28),
    Column(LOCATION),
)
QUERY_COLUMNS = (Column("category", 16), Column("query", 48), Column("count", 5, right=True), Column("expected"))


def _expected(keys: Sequence[str]) -> str:
    """The first `SHOWN_EXPECTED` keys, and how many more there are."""
    shown = _cell(keys[:SHOWN_EXPECTED])
    return f"{shown}, … {len(keys) - SHOWN_EXPECTED} more" if len(keys) > SHOWN_EXPECTED else shown


def render_corpus(corpus: Corpus, description: str) -> str:
    """A markdown page with one row per entity: its key and the facts queries are made from."""
    rows = (
        [entity.key, *(_cell(entity.facts[fact]) for fact in (DESCRIPTION, IDENTIFIER, CUSTOMER, LOCATION))]
        for entity in corpus.entities
    )
    return f"""# Search benchmark corpus

{description}

{UPDATE}

Every entity, anchors first, with the facts queries are made from: a query made from a fact expects every entity
that holds it. The indexed models hold much more, see `show_corpus` in the README.

{_table(CORPUS_COLUMNS, rows)}
"""


def render_queries(queries: Sequence[LabelledQuery], description: str) -> str:
    """A markdown page with one row per query: its category, text and the entities it expects."""
    rows = (
        [query.category.value, f"`{query.text}`", str(len(query.expected)), _expected(query.expected)]
        for query in queries
    )
    return f"""# Search benchmark generated queries

{description}

{UPDATE}

The queries `perturb.py` makes from the corpus, with the entities they expect. Only the first {SHOWN_EXPECTED} expected
keys are shown; `count` is all of them.

{_table(QUERY_COLUMNS, rows)}
"""
