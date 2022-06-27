from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle
from test_orchestrator.product_blocks.test_product_blocks import (
    TestProductBlock,
    TestProductBlockInactive,
    TestProductBlockProvisioning,
)


class TestProductInactive(SubscriptionModel, is_base=True):
    testproduct: TestProductBlockInactive


class TestProductProvisioning(TestProductInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    testproduct: TestProductBlockProvisioning


class TestProduct(TestProductProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    testproduct: TestProductBlock
