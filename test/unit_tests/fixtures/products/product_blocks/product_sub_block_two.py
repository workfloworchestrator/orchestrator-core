import pytest

from orchestrator.db import ProductBlockTable, db
from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product_sub_block_two():
    class SubBlockTwoForTestInactive(ProductBlockModel, product_block_name="SubBlockTwoForTest"):
        int_field_2: int  # TODO #430 inactive productblocks should not have required fields

    class SubBlockTwoForTestProvisioning(SubBlockTwoForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        int_field_2: int

    class SubBlockTwoForTest(SubBlockTwoForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        int_field_2: int

    return SubBlockTwoForTestInactive, SubBlockTwoForTestProvisioning, SubBlockTwoForTest


@pytest.fixture
def test_product_sub_block_two_db(resource_type_int_2):
    sub_block = ProductBlockTable(
        name="SubBlockTwoForTest", description="Test Sub Block Two", tag="TEST", status="active"
    )

    sub_block.resource_types = [resource_type_int_2]

    db.session.add(sub_block)
    db.session.commit()
    return sub_block
