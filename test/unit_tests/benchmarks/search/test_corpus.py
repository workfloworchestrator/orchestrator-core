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

from collections.abc import Iterator

import pytest
from pydantic import BaseModel

from test.benchmarks.search.corpus import CUSTOMER, DESCRIPTION, Corpus, CorpusEntity, build_corpus, scoped_rng
from test.benchmarks.search.profiles import network_services
from test.benchmarks.search.profiles.network_services import IP_PEERING, NetworkServicesProfile, ServicePortBlock


def ports(model: BaseModel) -> Iterator[ServicePortBlock]:
    """The port blocks anywhere in `model`, in field order: the A-end first."""
    for value in model.__dict__.values():
        items = value if isinstance(value, list) else [value]
        for item in items:
            if isinstance(item, ServicePortBlock):
                yield item
            elif isinstance(item, BaseModel):
                yield from ports(item)


def test_same_seed_gives_same_corpus():
    assert build_corpus(NetworkServicesProfile(), 1, 200) == build_corpus(NetworkServicesProfile(), 1, 200)


def test_other_seed_gives_other_corpus():
    assert build_corpus(NetworkServicesProfile(), 1, 200) != build_corpus(NetworkServicesProfile(), 2, 200)


def test_a_smaller_corpus_is_the_start_of_a_larger_one():
    small, large = (build_corpus(NetworkServicesProfile(), 1, size) for size in (100, 200))

    assert large.entities[: len(small.entities)] == small.entities


def test_drawing_more_for_one_entity_leaves_the_others_unchanged(monkeypatch):
    def is_peering(entity):
        return entity.model.product.name == IP_PEERING.name

    before = build_corpus(NetworkServicesProfile(), 1, 200)
    draw_peering = network_services._draw_peering
    # Every IP peering now draws an extra value: with one shared generator, every entity after it would change.
    monkeypatch.setattr(network_services, "_draw_peering", lambda rng: (rng.random(), draw_peering(rng))[1])
    after = build_corpus(NetworkServicesProfile(), 1, 200)

    assert any(map(is_peering, before.entities))
    assert [e for e in after.entities if not is_peering(e)] == [e for e in before.entities if not is_peering(e)]
    assert [e for e in after.entities if is_peering(e)] != [e for e in before.entities if is_peering(e)]


@pytest.mark.parametrize(
    "scope",
    [
        pytest.param((), id="no scope"),
        pytest.param(("entity", 3), id="entity"),
        pytest.param(("exact", "gen-3"), id="query"),
    ],
)
def test_scoped_rng_is_reproducible(scope):
    assert scoped_rng(1, *scope).random() == scoped_rng(1, *scope).random()


@pytest.mark.parametrize(
    "first, second",
    [
        pytest.param((1, "entity", 3), (2, "entity", 3), id="other seed"),
        pytest.param((1, "entity", 3), (1, "entity", 4), id="other entity"),
        pytest.param((1, "exact", "gen-3"), (1, "prefix", "gen-3"), id="other category"),
    ],
)
def test_scoped_rng_differs_per_scope(first, second):
    assert scoped_rng(*first).random() != scoped_rng(*second).random()


@pytest.mark.parametrize("size", [0, 1, 200])
def test_corpus_holds_anchors_and_requested_entities(size):
    anchors = len(NetworkServicesProfile().anchors())

    assert len(build_corpus(NetworkServicesProfile(), 1, size).entities) == anchors + size


def test_anchors_do_not_depend_on_seed():
    first, second = (build_corpus(NetworkServicesProfile(), seed, 0) for seed in (1, 2))

    assert first.entities == second.entities


def test_no_two_entities_share_an_a_end_port():
    corpus = build_corpus(NetworkServicesProfile(), 1, 500)
    # Services without a port, such as the LIR prefix anchor, have no A-end to share.
    a_ends = [
        (a_end.node.node_name, a_end.port_name)
        for entity in corpus.entities
        if (a_end := next(ports(entity.model), None))
    ]

    assert len(set(a_ends)) == len(a_ends)


def test_generated_entities_stay_clear_of_anchor_nodes_and_customer_locations():
    profile = NetworkServicesProfile()
    corpus = build_corpus(profile, 1, 500)
    generated = [entity for entity in corpus.entities if entity.key.startswith("gen-")]
    nodes = {port.node.node_name for entity in generated for port in ports(entity.model)}
    pairs = {
        (entity.facts[CUSTOMER][0].split()[0], port.node.city) for entity in generated for port in ports(entity.model)
    }

    assert generated
    assert not nodes & profile.reserved_nodes()
    assert not pairs & profile.reserved_pairs()


def test_reserved_nodes_hold_the_anchors_and_their_prefix_neighbours():
    assert {"ams001a-rt01", "ams001a-rt10", "ams001a-rt11", "ams001a-rt12", "rtd001a-rt07", "ehv001a-rt03"} <= (
        NetworkServicesProfile().reserved_nodes()
    )


def test_corpus_has_near_miss_anchors():
    keys = build_corpus(NetworkServicesProfile(), 1, 0).by_key.keys()

    assert {"ams001a-rt01", "ams001a-rt10", "asv001a-rt01", "twin-ehv002a-mst001a", "twin-ehv001a-mst002a"} <= keys


def test_twin_anchors_differ_only_in_the_order_of_their_characters():
    by_key = build_corpus(NetworkServicesProfile(), 1, 0).by_key
    first, second = (by_key[key].facts[DESCRIPTION][0] for key in ("twin-ehv002a-mst001a", "twin-ehv001a-mst002a"))

    assert first != second
    assert sorted(first) == sorted(second)


def test_too_large_a_corpus_raises():
    with pytest.raises(ValueError, match="has room for"):
        build_corpus(NetworkServicesProfile(), 1, 1_000_000)


class _Clashing:
    name = "clashing"

    def anchors(self):
        entity = CorpusEntity(
            "a", NetworkServicesProfile().anchors()[0].entity_id, NetworkServicesProfile().anchors()[0].model, {}
        )
        return [entity, entity]

    def generate(self, seed, count):
        return []


@pytest.mark.parametrize("profile", [_Clashing()])
def test_duplicate_entities_raise(profile):
    with pytest.raises(ValueError, match="duplicate entity"):
        build_corpus(profile, 1, 0)


def test_by_key_maps_keys_to_entities():
    corpus = build_corpus(NetworkServicesProfile(), 1, 3)

    assert isinstance(corpus, Corpus)
    assert set(corpus.by_key) == {entity.key for entity in corpus.entities}
