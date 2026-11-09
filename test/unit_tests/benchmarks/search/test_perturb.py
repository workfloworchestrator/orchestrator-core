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

from test.benchmarks.search import perturb as perturb_module
from test.benchmarks.search.corpus import build_corpus
from test.benchmarks.search.perturb import (
    GENERATORS,
    Category,
    case_punctuation,
    generate_queries,
    prefix,
    reorder,
    sample_sources,
    typo,
)
from test.benchmarks.search.profiles.network_services import NetworkServicesProfile


def test_typo_changes_one_word_of_a_description():
    text = "Almere Port alm-rt09 et-0/0/1 for Silverline Museum"
    result = typo(text, Random(1))

    changed = [(a, b) for a, b in zip(text.split(), result.split()) if a != b]
    assert len(changed) == 1
    assert sorted(changed[0][0]) == sorted(changed[0][1])


def test_generated_typo_queries_mistype_a_customer_and_expect_all_of_its_services():
    corpus = build_corpus(NetworkServicesProfile(), 1, 100)

    typos = [query for query in generate_queries(corpus, 10, 1) if query.category == Category.CUSTOMER_TYPO]
    assert typos
    for query in typos:
        customer = corpus.by_key[query.expected[0]].facts["customer"][0]
        assert query.text != customer
        assert sorted(query.text) == sorted(customer)
        assert set(query.expected) == {e.key for e in corpus.entities if customer in e.facts["customer"]}


@pytest.mark.parametrize("text", ["Rotterdam", "Silverline Museum", "Greenfield"])
def test_typo_never_swaps_equal_letters(text):
    assert all(typo(text, Random(seed)) != text for seed in range(20))


def test_generated_multi_field_queries_join_customer_and_location_and_expect_every_match():
    corpus = build_corpus(NetworkServicesProfile(), 1, 100)

    queries = [q for q in generate_queries(corpus, 10, 1) if q.category == Category.MULTI_FIELD]
    assert queries
    for query in queries:
        # Every expected entity holds the queried customer and location, but only the source made the text, from the
        # first value of each: another may hold the location as a B-end.
        sources = [
            (customer, location)
            for key in query.expected
            for customer, location in [(corpus.by_key[key].facts[fact][0] for fact in ("customer", "location"))]
            if query.text == f"{customer} {location}"
        ]
        assert sources
        customer, location = sources[0]
        assert set(query.expected) == {
            e.key for e in corpus.entities if customer in e.facts["customer"] and location in e.facts["location"]
        }


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


@pytest.mark.parametrize("removed", list(GENERATORS))
def test_removing_a_category_leaves_the_other_queries_unchanged(monkeypatch, removed):
    corpus = build_corpus(NetworkServicesProfile(), 1, 100)
    before = generate_queries(corpus, 10, 1)
    monkeypatch.setattr(
        perturb_module, "GENERATORS", {category: v for category, v in GENERATORS.items() if category != removed}
    )

    assert generate_queries(corpus, 10, 1) == [query for query in before if query.category != removed]


@pytest.mark.parametrize("count", [0, 10, 200])
def test_sample_sources_draws_count_distinct_entities(count):
    entities = build_corpus(NetworkServicesProfile(), 1, 100).entities
    sampled = sample_sources(entities, count, 1)

    assert len(sampled) == min(count, len(entities))
    assert len({entity.key for entity in sampled}) == len(sampled)


def test_removing_an_unsampled_entity_leaves_the_sample_unchanged():
    entities = build_corpus(NetworkServicesProfile(), 1, 100).entities
    sampled = sample_sources(entities, 10, 1)
    unsampled = next(entity for entity in entities if entity not in sampled)

    assert sample_sources([entity for entity in entities if entity != unsampled], 10, 1) == sampled


def test_removing_a_sampled_entity_keeps_the_rest_of_the_sample():
    entities = build_corpus(NetworkServicesProfile(), 1, 100).entities
    removed, *kept = sample_sources(entities, 10, 1)

    assert sample_sources([entity for entity in entities if entity != removed], 10, 1)[:-1] == kept
