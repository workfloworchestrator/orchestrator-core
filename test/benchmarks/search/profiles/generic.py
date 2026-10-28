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

Products are a service port, a light path, an L2VPN and an IP peering, shaped like the subscriptions of a network
orchestrator built on orchestrator-core: the root fields of a `SubscriptionModel` and its product, and product blocks
nested four to six deep (a virtual circuit with service attach points, each on a port on a node). Every block carries
the ids `ProductBlockModel` gives it, and the blocks carry inventory ids, flags and enums next to the names search is
for, so that most indexed fields are noise, as in production.

Descriptions are short codes, not prose: `NWR LP AMS001A-RTD001A 10 Gbit/s` is customer abbreviation, product tag,
sites and speed. Sites, node numbers and customers come in confusable groups, and every customer runs several
services, as search has to tell those apart.
"""

from collections.abc import Iterator, Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from ipaddress import ip_network
from itertools import count as counter
from itertools import islice
from random import Random
from typing import NamedTuple
from uuid import UUID, uuid5

from pydantic import BaseModel

from test.benchmarks.search.corpus import CUSTOMER, DESCRIPTION, IDENTIFIER, LOCATION, CorpusEntity

NAMESPACE = UUID("5b1b3c1e-0000-4000-8000-000000000001")

# (city, site prefix). Neighbouring entries are deliberate near-misses of each other.
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
SITES_PER_CITY = 2


class Customer(NamedTuple):
    name: str
    abbreviation: str


# Customers of one family (the first word) are near-misses, and so are their abbreviations.
CUSTOMERS = [
    Customer("Northwind Research", "NWR"),
    Customer("Northwind Labs", "NWL"),
    Customer("Bluefin University", "BFU"),
    Customer("Bluefin Hospital", "BFH"),
    Customer("Redwood Institute", "RWI"),
    Customer("Redwood Libraries", "RWL"),
    Customer("Silverline Museum", "SLM"),
    Customer("Silverline Archives", "SLA"),
    Customer("Greenfield College", "GFC"),
    Customer("Greenfield Observatory", "GFO"),
]


class Product(NamedTuple):
    name: str
    tag: str
    min_ends: int
    max_ends: int


SERVICE_PORT = Product("Service Port", "SP", 1, 1)
LIGHT_PATH = Product("Light Path", "LP", 2, 2)
L2VPN = Product("L2VPN", "L2VPN", 2, 4)
IP_PEERING = Product("IP Peering", "IP", 1, 1)
PRODUCTS = [SERVICE_PORT, LIGHT_PATH, L2VPN, IP_PEERING]

PORT_NAMES = ["et-0/0/{n}", "xe-1/2/{n}", "ge-0/1/{n}", "et-3/0/{n}"]
SPEEDS = [1000, 10000, 100000]
STATUSES = ["active", "provisioning", "terminated"]
STATUS_WEIGHTS = [17, 1, 2]
NODE_ROLE = "rt"
NODES_PER_SITE = 12
PORTS_PER_CARD = 8
# Node names kept free of generated entities besides the anchors' own, so that the hand-written prefix query
# `ams001a-rt1` has a closed set of answers: the anchors ams001a-rt01 and ams001a-rt10.
NEIGHBOUR_NODES = frozenset({"ams001a-rt11", "ams001a-rt12"})
# Draws without a fresh identifier in a row after which the profile is full.
MAX_ATTEMPTS = 200
FIRST_START_DATE = datetime(2018, 1, 1)


class End(NamedTuple):
    """Where a service lands: the city, site and node number, and the port on the node.

    A service's first end is its A-end, the others are its B-ends. Queries are made from the A-end. No two services
    share an A-end port, but many share a node.
    """

    city: str
    code: str
    site: int
    number: int
    port_name: str
    vlan: int

    @property
    def site_code(self) -> str:
        return f"{self.code.upper()}{self.site:03d}A"

    @property
    def node_name(self) -> str:
        return f"{self.site_code.lower()}-{NODE_ROLE}{self.number:02d}"

    @property
    def identifier(self) -> str:
        return f"{self.node_name} {self.port_name}"


class Peering(NamedTuple):
    prefix: str
    asn: int


class PortMode(StrEnum):
    TAGGED = "tagged"
    UNTAGGED = "untagged"


class ProductBlock(BaseModel):
    """The fields orchestrator-core's `ProductBlockModel` gives every block."""

    name: str
    subscription_instance_id: UUID
    owner_subscription_id: UUID
    label: str | None = None


class NodeBlock(ProductBlock):
    node_name: str
    site_code: str
    city: str
    node_role: str
    inventory_id: int


class ServicePortBlock(ProductBlock):
    port_name: str
    port_speed: int
    port_mode: PortMode
    admin_state: str
    lldp: bool
    inventory_id: int
    node: NodeBlock


class ServiceAttachPointBlock(ProductBlock):
    vlanrange: str
    port: ServicePortBlock


class LightPathCircuitBlock(ProductBlock):
    service_speed: int
    speed_policer: bool
    remote_port_shutdown: bool
    inventory_id: int
    saps: list[ServiceAttachPointBlock]


class EsiBlock(ProductBlock):
    saps: list[ServiceAttachPointBlock]


class L2vpnCircuitBlock(ProductBlock):
    service_speed: int
    speed_policer: bool
    vlan_retagging: bool
    bum_filter: bool
    inventory_id: int
    esis: list[EsiBlock]


class PeerBlock(ProductBlock):
    ipv4_remote_address: str
    bfd: bool
    sap: ServiceAttachPointBlock


class IpPeeringBlock(ProductBlock):
    peer_name: str
    asn: int
    service_speed: int
    prefixes: list[str]
    peers: list[PeerBlock]


class ProductInfo(BaseModel):
    """The product, as orchestrator-core's `ProductModel`."""

    product_id: UUID
    name: str
    description: str
    product_type: str
    tag: str
    status: str


class NetworkService(BaseModel):
    """What gets indexed: the root of a subscription-like entity, with one product-specific block."""

    subscription_id: UUID
    description: str
    status: str
    insync: bool
    start_date: datetime
    version: int
    customer_id: str
    customer_name: str
    customer_abbreviation: str
    product: ProductInfo
    port: ServicePortBlock | None = None
    vc: LightPathCircuitBlock | L2vpnCircuitBlock | None = None
    ip_peering: IpPeeringBlock | None = None

    @property
    def ports(self) -> list[ServicePortBlock]:
        """The ports of the service, A-end first. A property, not a field: it is not indexed."""
        match self.port, self.vc, self.ip_peering:
            case ServicePortBlock() as port, _, _:
                return [port]
            case _, LightPathCircuitBlock() as vc, _:
                return [sap.port for sap in vc.saps]
            case _, L2vpnCircuitBlock() as vc, _:
                return [sap.port for esi in vc.esis for sap in esi.saps]
            case _, _, IpPeeringBlock() as ip:
                return [peer.sap.port for peer in ip.peers]
        return []


def _id(*parts: object) -> UUID:
    return uuid5(NAMESPACE, ":".join(map(str, parts)))


def _inventory_id(*parts: object) -> int:
    """A six-digit id, as an inventory system hands out: never a peer ASN or a vlan."""
    return 100_000 + _id("inventory", *parts).int % 900_000


def _flag(entity_id: UUID, bit: int) -> bool:
    return bool(entity_id.int >> bit & 1)


def _speed(mbits: int) -> str:
    return f"{mbits // 1000} Gbit/s"


def _family(customer: str) -> str:
    return customer.split()[0]


def _node(end: End) -> NodeBlock:
    """The node block, the same in every service on that node: it is owned by the node's own subscription."""
    return NodeBlock(
        name="Node",
        subscription_instance_id=_id("node-block", end.node_name),
        owner_subscription_id=_id("node", end.node_name),
        node_name=end.node_name,
        site_code=end.site_code,
        city=end.city,
        node_role="core" if end.number <= 2 else "access",
        inventory_id=_inventory_id("node", end.node_name),
    )


def _port(end: End, speed: int, mode: PortMode) -> ServicePortBlock:
    """The port block, owned by the port's own subscription."""
    return ServicePortBlock(
        name="Service Port",
        subscription_instance_id=_id("port-block", end.identifier),
        owner_subscription_id=_id("port", end.identifier),
        port_name=end.port_name,
        port_speed=speed,
        port_mode=mode,
        admin_state="enabled",
        lldp=end.number % 2 == 0,
        inventory_id=_inventory_id("port", end.identifier),
        node=_node(end),
    )


def _sap(entity_id: UUID, index: int, end: End, speed: int) -> ServiceAttachPointBlock:
    return ServiceAttachPointBlock(
        name="Service Attach Point",
        subscription_instance_id=_id(entity_id, "sap", index),
        owner_subscription_id=entity_id,
        vlanrange=str(end.vlan),
        port=_port(end, speed, PortMode.TAGGED),
    )


def _description(product: Product, customer: Customer, ends: Sequence[End], speed: int, mode: PortMode) -> str:
    """`ABBR TAG SITES speed`: sites sorted, a multipoint service names its first three distinct ones."""
    sites = sorted({end.site_code for end in ends})[:3] if product.max_ends > 2 else sorted(e.site_code for e in ends)
    tag = f"{product.tag} {mode.value.upper()}" if product == SERVICE_PORT else product.tag
    return f"{customer.abbreviation} {tag} {'-'.join(sites)} {_speed(speed)}"


def _light_path(entity_id: UUID, ends: Sequence[End], speed: int) -> LightPathCircuitBlock:
    return LightPathCircuitBlock(
        name="Light Path Virtual Circuit",
        subscription_instance_id=_id(entity_id, "vc"),
        owner_subscription_id=entity_id,
        service_speed=speed,
        speed_policer=_flag(entity_id, 1),
        remote_port_shutdown=_flag(entity_id, 2),
        inventory_id=_inventory_id(entity_id, "vc"),
        saps=[_sap(entity_id, index, end, speed) for index, end in enumerate(ends)],
    )


def _l2vpn(entity_id: UUID, ends: Sequence[End], speed: int) -> L2vpnCircuitBlock:
    esis = [
        EsiBlock(
            name="L2VPN ESI",
            subscription_instance_id=_id(entity_id, "esi", index),
            owner_subscription_id=entity_id,
            saps=[_sap(entity_id, index, end, speed)],
        )
        for index, end in enumerate(ends)
    ]
    return L2vpnCircuitBlock(
        name="L2VPN Virtual Circuit",
        subscription_instance_id=_id(entity_id, "vc"),
        owner_subscription_id=entity_id,
        service_speed=speed,
        speed_policer=_flag(entity_id, 1),
        vlan_retagging=_flag(entity_id, 2),
        bum_filter=_flag(entity_id, 3),
        inventory_id=_inventory_id(entity_id, "vc"),
        esis=esis,
    )


def _ip_peering(
    entity_id: UUID, customer: Customer, ends: Sequence[End], speed: int, peering: Peering
) -> IpPeeringBlock:
    peers = [
        PeerBlock(
            name="IP Peer",
            subscription_instance_id=_id(entity_id, "peer", index),
            owner_subscription_id=entity_id,
            ipv4_remote_address=str(ip_network(peering.prefix)[index + 1]),
            bfd=_flag(entity_id, 1),
            sap=_sap(entity_id, index, end, speed),
        )
        for index, end in enumerate(ends)
    ]
    return IpPeeringBlock(
        name="IP Peering",
        subscription_instance_id=_id(entity_id, "ip"),
        owner_subscription_id=entity_id,
        peer_name=customer.abbreviation,
        asn=peering.asn,
        service_speed=speed,
        prefixes=[peering.prefix],
        peers=peers,
    )


def _service(  # noqa: PLR0913
    key: str,
    entity_id: UUID,
    product: Product,
    customer: Customer,
    ends: Sequence[End],
    peering: Peering | None = None,
    speed: int = 10000,
    status: str = "active",
) -> CorpusEntity:
    """A service of `customer` over `ends`, the A-end first.

    Raises:
        ValueError: When an IP peering has no `peering`.
    """
    if product == IP_PEERING and peering is None:
        raise ValueError(f"An {product.name} needs a peering")
    mode = PortMode.UNTAGGED if product == SERVICE_PORT and _flag(entity_id, 0) else PortMode.TAGGED
    description = _description(product, customer, ends, speed, mode)
    model = NetworkService(
        subscription_id=entity_id,
        description=description,
        status=status,
        insync=status == "active",
        start_date=FIRST_START_DATE + timedelta(days=entity_id.int % 2500),
        version=1,
        customer_id=str(_id("customer", customer.name)),
        customer_name=customer.name,
        customer_abbreviation=customer.abbreviation,
        product=ProductInfo(
            product_id=_id("product", product.name),
            name=product.name,
            description=product.name,
            product_type=product.name.replace(" ", ""),
            tag=product.tag,
            status="active",
        ),
        port=_port(ends[0], speed, mode) if product == SERVICE_PORT else None,
        vc=(
            _light_path(entity_id, ends, speed)
            if product == LIGHT_PATH
            else _l2vpn(entity_id, ends, speed)
            if product == L2VPN
            else None
        ),
        ip_peering=_ip_peering(entity_id, customer, ends, speed, peering) if peering else None,
    )
    return CorpusEntity(
        key=key,
        entity_id=entity_id,
        model=model,
        # A service is also found by its B-ends, and a customer by its abbreviation: a query for those is right too.
        facts={
            DESCRIPTION: (description,),
            IDENTIFIER: tuple(end.node_name for end in ends),
            CUSTOMER: (customer.name, customer.abbreviation),
            LOCATION: tuple(end.city for end in ends),
        },
    )


def _anchor_models(profile: "GenericProfile") -> list[NetworkService]:
    return [anchor.model for anchor in profile.anchors() if isinstance(anchor.model, NetworkService)]


CUSTOMER_BY_NAME = {customer.name: customer for customer in CUSTOMERS}


class GenericProfile:
    """Generic network services with deliberate near-miss groups."""

    name = "generic"

    def anchors(self) -> Sequence[CorpusEntity]:
        def anchor(key: str, product: Product, customer: str, ends: Sequence[End], **kwargs: object) -> CorpusEntity:
            return _service(key, _id(key), product, CUSTOMER_BY_NAME[customer], ends, **kwargs)  # type: ignore[arg-type]

        return [
            # ams001a-rt01 against ams001a-rt10: one transposition apart.
            anchor(
                "ams001a-rt01", SERVICE_PORT, "Northwind Research", [End("Amsterdam", "ams", 1, 1, "et-0/0/1", 101)]
            ),
            anchor(
                "ams001a-rt10", SERVICE_PORT, "Bluefin University", [End("Amsterdam", "ams", 1, 10, "et-0/0/1", 102)]
            ),
            # Amsterdam against Amstelveen.
            anchor(
                "asv001a-rt01", SERVICE_PORT, "Redwood Institute", [End("Amstelveen", "asv", 1, 1, "et-0/0/1", 103)]
            ),
            # One customer on several services.
            anchor(
                "northwind-lightpath",
                LIGHT_PATH,
                "Northwind Research",
                [End("Amsterdam", "ams", 1, 7, "xe-1/2/4", 210), End("Rotterdam", "rtd", 1, 7, "xe-1/2/4", 210)],
            ),
            anchor(
                "northwind-peering",
                IP_PEERING,
                "Northwind Research",
                [End("Utrecht", "utr", 1, 2, "et-3/0/2", 305)],
                peering=Peering(prefix="192.0.2.0/24", asn=64500),
            ),
            # Rotterdam against Roermond, with B-ends in Eindhoven against Enschede.
            anchor(
                "rtd001a-rt01",
                L2VPN,
                "Silverline Museum",
                [End("Rotterdam", "rtd", 1, 1, "ge-0/1/3", 410), End("Eindhoven", "ehv", 1, 3, "ge-0/1/3", 410)],
            ),
            anchor(
                "rmd001a-rt01",
                L2VPN,
                "Silverline Archives",
                [End("Roermond", "rmd", 1, 1, "ge-0/1/3", 411), End("Enschede", "ens", 1, 3, "ge-0/1/3", 411)],
            ),
        ]

    def reserved_nodes(self) -> frozenset[str]:
        """Node names only anchors carry, so that a query for one has a closed set of answers."""
        return (
            frozenset(port.node.node_name for anchor in _anchor_models(self) for port in anchor.ports) | NEIGHBOUR_NODES
        )

    def reserved_pairs(self) -> frozenset[tuple[str, str]]:
        """(customer family, city) pairs only anchors carry: `bluefin amsterdam` must mean one anchor.

        A family is a customer's first word, as the near-miss customers (Bluefin University, Bluefin Hospital) share
        it and a query names the family as often as the full customer.
        """
        return frozenset(
            (_family(anchor.customer_name), port.node.city) for anchor in _anchor_models(self) for port in anchor.ports
        )

    def generate(self, rng: Random, count: int) -> Sequence[CorpusEntity]:
        used = {f"{port.node.node_name} {port.port_name}" for anchor in _anchor_models(self) for port in anchor.ports}
        entities = list(islice(self._generate(rng, used), count))
        if len(entities) < count:
            raise ValueError(f"The generic profile has room for {len(entities)} entities, {count} requested")
        return entities

    def _generate(self, rng: Random, used: set[str]) -> Iterator[CorpusEntity]:
        """Entities until `MAX_ATTEMPTS` draws in a row clashed with an anchor or an earlier entity."""
        nodes, pairs = self.reserved_nodes(), self.reserved_pairs()

        def clashes(customer: Customer, ends: Sequence[End]) -> bool:
            return ends[0].identifier in used or any(
                end.node_name in nodes or (_family(customer.name), end.city) in pairs for end in ends
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
            peering = _draw_peering(rng) if product == IP_PEERING else None
            speed = rng.choice(SPEEDS)
            status = rng.choices(STATUSES, STATUS_WEIGHTS)[0]
            entity_id = UUID(int=rng.getrandbits(128), version=4)
            yield _service(f"gen-{index}", entity_id, product, customer, ends, peering, speed, status)


def _draw_end(rng: Random, vlan: int) -> End:
    city, code = rng.choice(LOCATIONS)
    site = rng.randint(1, SITES_PER_CITY)
    # Node numbers cluster, so that neighbours such as rt01 and rt10 exist for most sites.
    number = rng.randint(1, NODES_PER_SITE)
    port_name = rng.choice(PORT_NAMES).format(n=rng.randint(0, PORTS_PER_CARD - 1))
    return End(city, code, site, number, port_name, vlan)


def _draw(rng: Random) -> tuple[Product, Customer, list[End]]:
    """A random product and customer, and the ends of the service: an A-end, and B-ends for a light path or L2VPN."""
    product, customer = rng.choice(PRODUCTS), rng.choice(CUSTOMERS)
    vlan = rng.randint(100, 4000)
    ends = [_draw_end(rng, vlan) for _ in range(rng.randint(product.min_ends, product.max_ends))]
    return product, customer, ends


def _draw_peering(rng: Random) -> Peering:
    return Peering(prefix=f"198.51.{rng.randint(0, 255)}.0/24", asn=rng.randint(64512, 65534))
