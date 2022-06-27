from ipaddress import IPv4Address, IPv6Address

import structlog

from orchestrator.devtools.populator import Populator
from orchestrator.types import UUIDstr

logger = structlog.get_logger(__name__)


class TestProductPopulator(Populator):
    def __init__(
        self,
        an_int: int,
        a_str: str,
        a_bool: bool,
        an_uuid: UUIDstr,
        an_ipv4: IPv4Address,
        an_ipv6: IPv6Address,
    ):
        self.log = logger.bind()

        self.product_name = "Test Product"
        self.endpoint_description = "Test Product Endpoint"
        self.log = logger.bind(organisation="Test")

        self.an_int = an_int
        self.a_str = a_str
        self.a_bool = a_bool
        self.an_uuid = an_uuid
        self.an_ipv4 = str(an_ipv4)
        self.an_ipv6 = str(an_ipv6)

        super().__init__(self.product_name)

    def add_default_values(self) -> None:
        super().add_default_values()
        self.default_input_values.update(
            {
                "an_int": self.an_int,
                "a_str": self.a_str,
                "a_bool": self.a_bool,
                "an_uuid": self.an_uuid,
                "an_ipv4": self.an_ipv4,
                "an_ipv6": self.an_ipv6,
            }
        )
