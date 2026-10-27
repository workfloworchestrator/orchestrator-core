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

"""Query generation: take a fact of an entity and perturb it the way a user would mistype it.

The entity a query was made from is its correct answer by construction. Every perturbation is a pure function of the
text and an `Random`, so the same corpus and seed give the same queries.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from random import Random

from test.benchmarks.search.corpus import CUSTOMER, DESCRIPTION, IDENTIFIER, LOCATION, Corpus

# Fewer characters than this leave nothing to find after a perturbation.
MIN_LENGTH = 5


class Category(str, Enum):
    EXACT = "exact"
    PREFIX = "prefix"
    TYPO = "typo"
    REORDER = "reorder"
    CASE_PUNCTUATION = "case_punctuation"
    IDENTIFIER = "identifier"
    MULTI_FIELD = "multi_field"
    NEGATIVE = "negative"


@dataclass(frozen=True)
class LabelledQuery:
    """A query with the entities it should find, in any order unless the ranking is part of the label.

    Attributes:
        text: The query text.
        category: What kind of query this is; metrics are reported per category.
        expected: Keys of the entities that should be found. Empty for a query that should find nothing.
        note: Why this is the intended behaviour. Only hand-written queries need one.
    """

    text: str
    category: Category
    expected: tuple[str, ...]
    note: str = ""


def typo(text: str, rng: Random) -> str:
    """Swap two neighbouring letters, or drop one, inside the first word of at least 4 letters."""
    positions = [m.start() + i for m in re.finditer(r"[A-Za-z]{4,}", text) for i in range(1, len(m.group()) - 1)]
    position = rng.choice(positions)
    return text[:position] + text[position + 1] + text[position] + text[position + 2 :]


def prefix(text: str, rng: Random) -> str:
    """The first 60 to 80 percent of the text, cut on a character."""
    return text[: max(3, round(len(text) * rng.uniform(0.6, 0.8)))]


def reorder(text: str, rng: Random) -> str:
    """The words in another order."""
    words = text.split()
    shuffled = rng.sample(words, len(words))
    return " ".join(shuffled if shuffled != words else words[::-1])


def case_punctuation(text: str, rng: Random) -> str:
    """Upper case, or separators swapped: `ams-rt07 et-0/0/1` as `AMS RT07 ET 0 0 1`."""
    return text.upper() if rng.random() < 0.5 else re.sub(r"[-/]+", " ", text)


def exact(text: str, rng: Random) -> str:  # noqa: ARG001
    return text


# Which fact each category perturbs, and how. A category is only generated for entities that have the fact.
GENERATORS: Mapping[Category, tuple[str, Callable[[str, Random], str]]] = {
    Category.EXACT: (DESCRIPTION, exact),
    Category.PREFIX: (DESCRIPTION, prefix),
    Category.TYPO: (LOCATION, typo),
    Category.REORDER: (DESCRIPTION, reorder),
    Category.CASE_PUNCTUATION: (IDENTIFIER, case_punctuation),
    Category.IDENTIFIER: (IDENTIFIER, exact),
    Category.MULTI_FIELD: (CUSTOMER, exact),
}


def generate_queries(corpus: Corpus, per_category: int, seed: int) -> list[LabelledQuery]:
    """`per_category` queries for each generated category, made from entities drawn with `seed`.

    A query is dropped if the perturbed text is no longer than `MIN_LENGTH`. Queries whose text is shared by several
    entities (a customer, a location) expect all of them.
    """
    rng = Random(seed)  # noqa: S311 - reproducible, not secret
    sampled = rng.sample(corpus.entities, min(per_category, len(corpus.entities)))
    queries = []
    for category, (fact, perturb) in GENERATORS.items():
        for entity in sampled:
            text = perturb(entity.facts[fact], rng)
            if len(text) < MIN_LENGTH:
                continue
            expected = tuple(e.key for e in corpus.entities if e.facts[fact] == entity.facts[fact])
            queries.append(LabelledQuery(text=text, category=category, expected=expected))
    return queries
