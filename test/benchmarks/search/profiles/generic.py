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

"""The default profile: generic network services, not specific to any organisation.

Products are a port, a light path, an L2VPN and an IP peering. Each subscription nests blocks and lists like a real
one (a customer block, a list of service ports each with a node, an optional IP block) so that the index has many
fields at different depths. Locations come in confusable pairs, node numbers in confusable neighbours, and every
customer runs several services, as search has to tell those apart.
"""

from collections.abc import Iterator, Sequence
from itertools import count as counter
from itertools import islice
from random import Random
from typing import NamedTuple
from uuid import UUID, uuid5

from pydantic import BaseModel

from test.benchmarks.search.corpus import CUSTOMER, DESCRIPTION, IDENTIFIER, LOCATION, CorpusEntity

NAMESPACE = UUID("5b1b3c1e-0000-4000-8000-000000000001")

# (city, node code). Neighbouring entries are deliberate near-misses of each other.
LOCATIONS = [
    ("Amsterdam", "ams"),
    ("Amstelveen", "asv"),
    ("Rotterdam", "rtd"),
    ("Roermond", "rmd"),
    ("Utrecht", "utr"),
    ("Maastricht", "mst"),
    ("Groningen", "grq"),
    ("Gorinchem", "gor"),
    ("Eindhoven", "ehv"),
    ("Enschede", "ens"),
    ("Arnhem", "arn"),
    ("Almere", "alm"),
]

CUSTOMERS = [
    "Northwind Research",
    "Northwind Labs",
    "Bluefin University",
    "Bluefin Hospital",
    "Redwood Institute",
    "Redwood Libraries",
    "Silverline Museum",
    "Silverline Archives",
    "Greenfield College",
    "Greenfield Observatory",
]

PRODUCTS = ["Port", "Light Path", "L2VPN", "IP Peering"]
TWO_ENDED = frozenset({"Light Path", "L2VPN"})
PORT_NAMES = ["et-0/0/{n}", "xe-1/2/{n}", "ge-0/1/{n}", "et-3/0/{n}"]
SPEEDS = [1000, 10000, 100000]
NODE_ROLE = "rt"
PORTS_PER_CARD = 8
# Node names kept free of generated entities besides the anchors' own, so that the hand-written prefix query
# `ams-rt1` has a closed set of answers: the anchors ams-rt01 and ams-rt10.
NEIGHBOUR_NODES = frozenset({"ams-rt11", "ams-rt12"})
# Draws without a fresh identifier in a row after which the profile is full.
MAX_ATTEMPTS = 200


class End(NamedTuple):
    """Where a service lands: the node's city, code and number, and the port on it.

    A service's first end is its A-end: its description, and the queries made from it, name that end.
    """

    city: str
    code: str
    number: int
    port_name: str
    vlan: int

    @property
    def node_name(self) -> str:
        return _node_name(self.code, self.number)

    @property
    def identifier(self) -> str:
        return f"{self.node_name} {self.port_name}"


class CustomerBlock(BaseModel):
    customer_id: UUID
    name: str


class NodeBlock(BaseModel):
    node_name: str
    location: str


class ServicePort(BaseModel):
    port_name: str
    port_speed: int
    vlan_id: int
    node: NodeBlock


class IpBlock(BaseModel):
    prefix: str
    peer_asn: int


class NetworkService(BaseModel):
    """What gets indexed: the root of a subscription-like entity."""

    subscription_id: UUID
    description: str
    status: str
    product_name: str
    customer: CustomerBlock
    ports: list[ServicePort]
    ip: IpBlock | None = None


def _customer(name: str) -> CustomerBlock:
    return CustomerBlock(customer_id=uuid5(NAMESPACE, f"customer:{name}"), name=name)


def _node_name(code: str, number: int) -> str:
    return f"{code}-{NODE_ROLE}{number:02d}"


def _family(customer: str) -> str:
    return customer.split()[0]


def _service(
    key: str,
    entity_id: UUID,
    product: str,
    customer: str,
    ends: Sequence[End],
    ip: IpBlock | None = None,
) -> CorpusEntity:
    """A service over `ends` of (city, node code, node number, port name, vlan id)."""
    ports = [
        ServicePort(
            port_name=port_name,
            port_speed=10000,
            vlan_id=vlan,
            node=NodeBlock(node_name=_node_name(code, number), location=city),
        )
        for city, code, number, port_name, vlan in ends
    ]
    first = ports[0]
    description = f"{first.node.location} {product} {first.node.node_name} {first.port_name} for {customer}"
    model = NetworkService(
        subscription_id=entity_id,
        description=description,
        status="active",
        product_name=product,
        customer=_customer(customer),
        ports=ports,
        ip=ip,
    )
    return CorpusEntity(
        key=key,
        entity_id=entity_id,
        model=model,
        # A service is also found by its B-end, so a query for that is right to return it.
        facts={
            DESCRIPTION: (description,),
            IDENTIFIER: tuple(_identifier(port) for port in ports),
            CUSTOMER: (customer,),
            LOCATION: tuple(port.node.location for port in ports),
        },
    )


def _identifier(port: ServicePort) -> str:
    return f"{port.node.node_name} {port.port_name}"


def _anchor_models(profile: "GenericProfile") -> list[NetworkService]:
    return [anchor.model for anchor in profile.anchors() if isinstance(anchor.model, NetworkService)]


class GenericProfile:
    """Generic network services with deliberate near-miss groups."""

    name = "generic"

    def anchors(self) -> Sequence[CorpusEntity]:
        def anchor(key: str, *args: object, **kwargs: object) -> CorpusEntity:
            return _service(key, uuid5(NAMESPACE, key), *args, **kwargs)  # type: ignore[arg-type]

        return [
            # ams-rt01 against ams-rt10: one transposition apart.
            anchor("ams-rt01", "Port", "Northwind Research", [("Amsterdam", "ams", 1, "et-0/0/1", 101)]),
            anchor("ams-rt10", "Port", "Bluefin University", [("Amsterdam", "ams", 10, "et-0/0/1", 102)]),
            # Amsterdam against Amstelveen.
            anchor("asv-rt01", "Port", "Redwood Institute", [("Amstelveen", "asv", 1, "et-0/0/1", 103)]),
            # One customer on several services.
            anchor(
                "northwind-lightpath",
                "Light Path",
                "Northwind Research",
                [("Amsterdam", "ams", 7, "xe-1/2/4", 210), ("Rotterdam", "rtd", 7, "xe-1/2/4", 210)],
            ),
            anchor(
                "northwind-peering",
                "IP Peering",
                "Northwind Research",
                [("Utrecht", "utr", 2, "et-3/0/2", 305)],
                ip=IpBlock(prefix="192.0.2.0/24", peer_asn=64500),
            ),
            # The same text in a description against a node name.
            anchor("rtd-rt01", "L2VPN", "Silverline Museum", [("Rotterdam", "rtd", 1, "ge-0/1/3", 410)]),
            anchor("rmd-rt01", "L2VPN", "Silverline Archives", [("Roermond", "rmd", 1, "ge-0/1/3", 411)]),
        ]

    def reserved_nodes(self) -> frozenset[str]:
        """Node names only anchors carry, so that a query for one has a closed set of answers."""
        return (
            frozenset(port.node.node_name for anchor in _anchor_models(self) for port in anchor.ports) | NEIGHBOUR_NODES
        )

    def reserved_pairs(self) -> frozenset[tuple[str, str]]:
        """(customer family, location) pairs only anchors carry: `bluefin amsterdam` must mean one anchor.

        A family is a customer's first word, as the near-miss customers (Bluefin University, Bluefin Hospital) share
        it and a query names the family as often as the full customer.
        """
        return frozenset(
            (_family(anchor.customer.name), port.node.location)
            for anchor in _anchor_models(self)
            for port in anchor.ports
        )

    def generate(self, rng: Random, count: int) -> Sequence[CorpusEntity]:
        used = {anchor.facts[IDENTIFIER][0] for anchor in self.anchors()}
        entities = list(islice(self._generate(rng, used), count))
        if len(entities) < count:
            raise ValueError(f"The generic profile has room for {len(entities)} entities, {count} requested")
        return entities

    def _generate(self, rng: Random, used: set[str]) -> Iterator[CorpusEntity]:
        """Entities until `MAX_ATTEMPTS` draws in a row clashed with an anchor or an earlier entity."""
        nodes, pairs = self.reserved_nodes(), self.reserved_pairs()

        def clashes(customer: str, ends: Sequence[End]) -> bool:
            return ends[0].identifier in used or any(
                end.node_name in nodes or (_family(customer), end.city) in pairs for end in ends
            )

        misses = 0
        for index in counter():
            product, customer, ends = _draw(rng)
            if clashes(customer, ends):
                misses += 1
                if misses == MAX_ATTEMPTS:
                    return
                continue
            misses = 0
            used.add(ends[0].identifier)
            ip = _draw_ip(rng) if product == "IP Peering" else None
            yield _service(f"gen-{index}", UUID(int=rng.getrandbits(128), version=4), product, customer, ends, ip)


def _draw(rng: Random) -> tuple[str, str, list[End]]:
    """A random product and customer, and the ends of the service: an A-end, and a B-end for a light path or an L2VPN."""
    city, code = rng.choice(LOCATIONS)
    # Node numbers cluster, so that neighbours such as rt01 and rt10 exist for most locations.
    number = rng.randint(1, 12)
    port_name = rng.choice(PORT_NAMES).format(n=rng.randint(0, PORTS_PER_CARD - 1))
    product, customer = rng.choice(PRODUCTS), rng.choice(CUSTOMERS)
    a_end = End(city, code, number, port_name, rng.randint(100, 4000))
    if product not in TWO_ENDED:
        return product, customer, [a_end]
    b_city, b_code = rng.choice(LOCATIONS)
    b_end = End(b_city, b_code, rng.randint(1, 12), rng.choice(PORT_NAMES).format(n=1), a_end.vlan)
    return product, customer, [a_end, b_end]


def _draw_ip(rng: Random) -> IpBlock:
    return IpBlock(prefix=f"198.51.{rng.randint(0, 255)}.0/24", peer_asn=rng.randint(64512, 65534))
