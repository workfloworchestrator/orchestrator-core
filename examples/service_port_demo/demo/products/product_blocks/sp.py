from typing import Optional

from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle, strEnum


class PortMode(strEnum):
    tagged = "tagged"
    untagged = "untagged"


class ServicePortBlockInactive(ProductBlockModel, product_block_name="service-port"):
    port_mode: Optional[PortMode] = None
    port_id: Optional[int] = None


class ServicePortBlockProvisioning(
    ServicePortBlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
):
    port_mode: PortMode
    port_id: int


class ServicePortBlock(ServicePortBlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    port_mode: PortMode
    port_id: int
