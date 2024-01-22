import pytest

from orchestrator.db import ProductBlockTable, db
from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product_sub_block_one():
    class SubBlockOneForTestInactive(ProductBlockModel, product_block_name="SubBlockOneForTest"):
        int_field: int | None = None
        str_field: str | None = None

    class SubBlockOneForTestProvisioning(SubBlockOneForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        int_field: int
        str_field: str | None = None

    class SubBlockOneForTest(SubBlockOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        int_field: int
        str_field: str

    return SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest


@pytest.fixture
def test_product_sub_block_one_db(resource_type_int, resource_type_str):
    sub_block = ProductBlockTable(
        name="SubBlockOneForTest", description="Test Sub Block One", tag="TEST", status="active"
    )

    sub_block.resource_types = [resource_type_int, resource_type_str]

    db.session.add(sub_block)
    db.session.commit()
    return sub_block
