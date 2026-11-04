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
text and a `Random`, so the same corpus and seed give the same queries.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from heapq import nsmallest
from itertools import product
from random import Random

from test.benchmarks.search.corpus import CUSTOMER, DESCRIPTION, IDENTIFIER, LOCATION, Corpus, CorpusEntity, scoped_rng

# Fewer characters than this leave nothing to find after a perturbation.
MIN_LENGTH = 5


class Category(str, Enum):
    EXACT = "exact"
    PREFIX = "prefix"
    TYPO = "typo"
    CUSTOMER_TYPO = "customer_typo"
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
    """Swap two different neighbouring letters inside one of the words of at least 4 letters."""
    positions = [
        m.start() + i
        for m in re.finditer(r"[A-Za-z]{4,}", text)
        for i in range(1, len(m.group()) - 1)
        # Swapping the "tt" of Rotterdam would leave it unchanged.
        if m.group()[i] != m.group()[i + 1]
    ]
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
    """Upper case, or separators swapped: `ams001a-rt07 et-0/0/1` as `AMS001A RT07 ET 0 0 1`."""
    return text.upper() if rng.random() < 0.5 else re.sub(r"[-/]+", " ", text)


def exact(text: str, rng: Random) -> str:  # noqa: ARG001
    return text


# Which facts each category joins and perturbs, and how. A category is only generated for entities that have them.
GENERATORS: Mapping[Category, tuple[tuple[str, ...], Callable[[str, Random], str]]] = {
    Category.EXACT: ((DESCRIPTION,), exact),
    Category.PREFIX: ((DESCRIPTION,), prefix),
    # A mistyped customer name: descriptions are codes with no word to mistype. It expects every service of the
    # customer, so Recall@10 is the share of the top 10 that is that customer's. Hand-written `typo` queries mistype
    # one field and expect one entity, which is why this is its own category.
    Category.CUSTOMER_TYPO: ((CUSTOMER,), typo),
    Category.REORDER: ((DESCRIPTION,), reorder),
    Category.CASE_PUNCTUATION: ((IDENTIFIER,), case_punctuation),
    Category.IDENTIFIER: ((IDENTIFIER,), exact),
    # Two facts from different blocks of the entity: together they say more than either alone, and every entity that
    # has both is a valid answer.
    Category.MULTI_FIELD: ((CUSTOMER, LOCATION), exact),
}


def answers(
    candidate: CorpusEntity, source: CorpusEntity, category: Category, facts: tuple[str, ...], text: str
) -> bool:
    """Whether `candidate` is a right answer to `text`, made from `facts` of `source`.

    It is when it holds the source's value of every fact among any of its own (a customer at a location, counting a
    light path with its B-end there). A prefix is answered by every entity with a value that starts with it, as
    `NWL IP GRQ002A 1` is the start of a 1 and of a 100 Gbit/s description alike.
    """
    if category == Category.PREFIX:
        return any(value.startswith(text) for fact in facts for value in candidate.facts[fact])
    return all(source.facts[fact][0] in candidate.facts[fact] for fact in facts)


def generate_queries(corpus: Corpus, per_category: int, seed: int) -> list[LabelledQuery]:
    """`per_category` queries for each generated category, made from entities drawn with `seed`.

    Every category uses the same entities (`sample_sources`). Each query is perturbed with its own `scoped_rng`, keyed
    by category and entity, so removing or changing a category, or a perturbation drawing more values, leaves the other
    queries as they were.
    """
    sampled = sample_sources(corpus.entities, per_category, seed)
    queries = (_query(corpus, category, entity, seed) for category, entity in product(GENERATORS, sampled))
    return [query for query in queries if query is not None]


def sample_sources(entities: Sequence[CorpusEntity], count: int, seed: int) -> list[CorpusEntity]:
    """The `count` entities ranked first by a random number drawn per entity key.

    The rank of an entity depends on its key only, not on its position, so adding or removing an entity (an anchor,
    say) changes the sample only when that entity itself ranks among the first `count`.
    """
    return nsmallest(count, entities, key=lambda entity: scoped_rng(seed, "sample", entity.key).random())


def _query(corpus: Corpus, category: Category, source: CorpusEntity, seed: int) -> LabelledQuery | None:
    """The `category` query made from `source`, or None when it has none.

    A query is made from the first value of each fact. There is none when `source` lacks one of the facts, as an IP
    prefix has no location, or when the perturbed text is shorter than `MIN_LENGTH`. It expects every entity that
    answers it (`answers`), not only `source`.
    """
    facts, perturb = GENERATORS[category]
    if not all(source.facts[fact] for fact in facts):
        return None
    text = perturb(" ".join(source.facts[fact][0] for fact in facts), scoped_rng(seed, category.value, source.key))
    if len(text) < MIN_LENGTH:
        return None
    expected = tuple(entity.key for entity in corpus.entities if answers(entity, source, category, facts, text))
    return LabelledQuery(text=text, category=category, expected=expected)
