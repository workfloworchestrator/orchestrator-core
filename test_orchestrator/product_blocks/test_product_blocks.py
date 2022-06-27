from ipaddress import IPv4Address, IPv6Address
from uuid import UUID

from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle


class TestProductBlockInactive(ProductBlockModel, product_block_name="Test Product Block"):
    an_int: int | None = None
    a_str: str | None = None
    a_bool: bool | None = None
    an_uuid: UUID | None = None
    an_ipv4: IPv4Address | None = None
    an_ipv6: IPv6Address | None = None


class TestProductBlockProvisioning(TestProductBlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    an_int: int
    a_str: str
    a_bool: bool | None = None
    an_uuid: UUID
    an_ipv4: IPv4Address | None = None
    an_ipv6: IPv6Address | None = None


class TestProductBlock(TestProductBlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    an_int: int
    a_str: str
    a_bool: bool
    an_uuid: UUID
    an_ipv4: IPv4Address
    an_ipv6: IPv6Address
