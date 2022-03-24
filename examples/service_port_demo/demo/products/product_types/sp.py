from enum import IntEnum
from typing import Optional

from demo.products.product_blocks.sp import ServicePortBlock, ServicePortBlockInactive, ServicePortBlockProvisioning

from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle


class PortSpeed(IntEnum):
    _1000 = 1000
    _10000 = 10000
    _40000 = 40000
    _100000 = 100000


class ServicePortInactive(
    SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.INITIAL, SubscriptionLifecycle.TERMINATED]
):
    port_speed: Optional[PortSpeed] = None
    port: ServicePortBlockInactive


class ServicePortProvisioning(
    ServicePortInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
):
    port_speed: PortSpeed
    port: ServicePortBlockProvisioning


class ServicePort(ServicePortProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    port_speed: PortSpeed
    port: ServicePortBlock
