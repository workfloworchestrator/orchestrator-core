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

# ruff: noqa: S311 - seeded, reproducible randomness is the point
from random import Random

import pytest

from test.benchmarks.search.corpus import build_corpus
from test.benchmarks.search.perturb import (
    GENERATORS,
    Category,
    case_punctuation,
    exact,
    generate_queries,
    prefix,
    reorder,
    typo,
)
from test.benchmarks.search.profiles.generic import GenericProfile


@pytest.mark.parametrize("perturb", [typo, prefix, reorder, case_punctuation, exact])
def test_perturbation_is_deterministic(perturb):
    text = "Amsterdam Port ams-rt01 et-0/0/1"

    assert perturb(text, Random(3)) == perturb(text, Random(3))


def test_typo_keeps_the_letters():
    result = typo("Amsterdam", Random(1))

    assert result != "Amsterdam"
    assert sorted(result) == sorted("Amsterdam")


def test_typo_changes_one_word_of_a_description():
    text = "Almere Port alm-rt09 et-0/0/1 for Silverline Museum"
    result = typo(text, Random(1))

    changed = [(a, b) for a, b in zip(text.split(), result.split()) if a != b]
    assert len(changed) == 1
    assert sorted(changed[0][0]) == sorted(changed[0][1])


def test_generated_typo_queries_expect_one_entity():
    corpus = build_corpus(GenericProfile(), 1, 100)

    typos = [query for query in generate_queries(corpus, 10, 1) if query.category == Category.TYPO]
    assert typos
    assert all(len(query.expected) == 1 for query in typos)
    assert all(query.text != corpus.by_key[query.expected[0]].facts["description"] for query in typos)


@pytest.mark.parametrize("text", ["Rotterdam", "Silverline Museum", "Greenfield"])
def test_typo_never_swaps_equal_letters(text):
    assert all(typo(text, Random(seed)) != text for seed in range(20))


def test_typo_without_a_long_word_raises():
    with pytest.raises(IndexError):
        typo("ab cd", Random(1))


def test_prefix_is_a_proper_prefix():
    text = "Amsterdam Port ams-rt01"

    assert text.startswith(result := prefix(text, Random(1)))
    assert len(result) < len(text)


def test_reorder_keeps_the_words_but_not_their_order():
    text = "one two three"
    result = reorder(text, Random(1))

    assert sorted(result.split()) == sorted(text.split())
    assert result != text


@pytest.mark.parametrize(
    "text,expected",
    [("ams-rt01 et-0/0/1", {"AMS-RT01 ET-0/0/1", "ams rt01 et 0 0 1"})],
)
def test_case_punctuation_changes_case_or_separators(text, expected):
    assert {case_punctuation(text, Random(seed)) for seed in range(10)} == expected


def test_generated_queries_cover_every_generated_category():
    queries = generate_queries(build_corpus(GenericProfile(), 1, 100), 10, 1)

    assert {query.category for query in queries} == set(GENERATORS)
    assert Category.NEGATIVE not in {query.category for query in queries}


def test_generated_queries_expect_their_source_entity():
    corpus = build_corpus(GenericProfile(), 1, 100)

    for query in generate_queries(corpus, 10, 1):
        assert query.expected
        assert set(query.expected) <= corpus.by_key.keys()


def test_generated_queries_are_deterministic():
    corpus = build_corpus(GenericProfile(), 1, 100)

    assert generate_queries(corpus, 10, 5) == generate_queries(corpus, 10, 5)
