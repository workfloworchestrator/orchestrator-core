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

import pytest

from test.benchmarks.search.corpus import IDENTIFIER, Corpus, CorpusEntity, build_corpus
from test.benchmarks.search.profiles.generic import GenericProfile


def test_same_seed_gives_same_corpus():
    assert build_corpus(GenericProfile(), 1, 200) == build_corpus(GenericProfile(), 1, 200)


def test_other_seed_gives_other_corpus():
    assert build_corpus(GenericProfile(), 1, 200) != build_corpus(GenericProfile(), 2, 200)


@pytest.mark.parametrize("size", [0, 1, 200])
def test_corpus_holds_anchors_and_requested_entities(size):
    anchors = len(GenericProfile().anchors())

    assert len(build_corpus(GenericProfile(), 1, size).entities) == anchors + size


def test_anchors_do_not_depend_on_seed():
    first, second = (build_corpus(GenericProfile(), seed, 0) for seed in (1, 2))

    assert first.entities == second.entities


def test_generated_identifiers_are_unique_and_clear_of_anchors():
    corpus = build_corpus(GenericProfile(), 1, 500)
    identifiers = [entity.facts[IDENTIFIER] for entity in corpus.entities]

    assert len(set(identifiers)) == len(identifiers)


def test_corpus_has_near_miss_anchors():
    keys = build_corpus(GenericProfile(), 1, 0).by_key.keys()

    assert {"ams-rt01", "ams-rt10", "asv-rt01"} <= keys


def test_too_large_a_corpus_raises():
    with pytest.raises(ValueError, match="has room for"):
        build_corpus(GenericProfile(), 1, 1_000_000)


class _Clashing:
    name = "clashing"

    def anchors(self):
        entity = CorpusEntity("a", GenericProfile().anchors()[0].entity_id, GenericProfile().anchors()[0].model, {})
        return [entity, entity]

    def generate(self, rng, count):
        return []


@pytest.mark.parametrize("profile", [_Clashing()])
def test_duplicate_entities_raise(profile):
    with pytest.raises(ValueError, match="duplicate entity"):
        build_corpus(profile, 1, 0)


def test_by_key_maps_keys_to_entities():
    corpus = build_corpus(GenericProfile(), 1, 3)

    assert isinstance(corpus, Corpus)
    assert set(corpus.by_key) == {entity.key for entity in corpus.entities}
