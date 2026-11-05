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
from dataclasses import replace

import pytest
from pydantic import BaseModel

from test.benchmarks.search.corpus import CUSTOMER, build_corpus
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


def test_a_smaller_corpus_is_the_start_of_a_larger_one():
    small, large = (build_corpus(NetworkServicesProfile(), 1, size) for size in (100, 200))

    assert large.entities[: len(small.entities)] == small.entities


def test_other_seed_gives_other_entities():
    first, second = (build_corpus(NetworkServicesProfile(), seed, 20) for seed in (1, 2))

    assert first.entities != second.entities


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


def test_too_large_a_corpus_raises():
    with pytest.raises(ValueError, match="has room for"):
        build_corpus(NetworkServicesProfile(), 1, 1_000_000)


class _Clashing:
    name = "clashing"

    def __init__(self, attribute):
        self.attribute = attribute

    def anchors(self):
        first, second = NetworkServicesProfile().anchors()[:2]
        return [first, replace(second, **{self.attribute: getattr(first, self.attribute)})]

    def generate(self, seed, count):
        return []


@pytest.mark.parametrize("attribute", ["key", "entity_id"])
def test_duplicate_entities_raise(attribute):
    with pytest.raises(ValueError, match=f"duplicate entity {attribute}s"):
        build_corpus(_Clashing(attribute), 1, 0)
