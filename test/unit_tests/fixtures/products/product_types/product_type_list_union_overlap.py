from uuid import uuid4

import pytest
from pydantic import conlist

from orchestrator.db import ProductTable, db
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle
from test.unit_tests.fixtures.products.product_blocks.product_block_one import DummyEnum


@pytest.fixture
def test_product_type_list_union_overlap(test_product_block_one, test_product_sub_block_one):
    ProductBlockOneForTestInactive, ProductBlockOneForTestProvisioning, ProductBlockOneForTest = test_product_block_one
    SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest = test_product_sub_block_one

    def list_of_ports(t):
        return conlist(t, min_length=1)

    class ProductListUnionInactive(SubscriptionModel, is_base=True):
        test_block: ProductBlockOneForTestInactive | None
        list_union_blocks: list_of_ports(ProductBlockOneForTestInactive | SubBlockOneForTestInactive)

    class ProductListUnionProvisioning(ProductListUnionInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_block: ProductBlockOneForTestProvisioning
        list_union_blocks: list_of_ports(ProductBlockOneForTestProvisioning | SubBlockOneForTestProvisioning)

    class ProductListUnion(ProductListUnionProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: ProductBlockOneForTest
        list_union_blocks: list_of_ports(ProductBlockOneForTest | SubBlockOneForTest)

    SUBSCRIPTION_MODEL_REGISTRY["ProductListUnion"] = ProductListUnion
    yield ProductListUnionInactive, ProductListUnionProvisioning, ProductListUnion
    del SUBSCRIPTION_MODEL_REGISTRY["ProductListUnion"]


@pytest.fixture
def test_product_list_union_overlap(test_product_block_one_db):
    product = ProductTable(
        name="ProductListUnionOverlap",
        description="Test List Union Product Overlap",
        product_type="Test",
        tag="Union",
        status="active",
    )

    product_block, product_sub_block = test_product_block_one_db
    product.product_blocks = [product_block, product_sub_block]
    db.session.add(product)
    db.session.commit()
    return product.product_id


@pytest.fixture
def sub_list_union_overlap_subscription_1(
    test_product_list_union_overlap,
    test_product_type_list_union_overlap,
    test_product_sub_block_one,
    test_product_block_one,
    sub_one_subscription_1,
):
    ProductListUnionInactive, _, ProductListUnion = test_product_type_list_union_overlap
    SubBlockOneForTestInactive, _, _ = test_product_sub_block_one
    ProductBlockOneForTestInactive, _, _ = test_product_block_one

    list_union_subscription_inactive = ProductListUnionInactive.from_product_id(
        product_id=test_product_list_union_overlap, customer_id=str(uuid4())
    )

    list_union_subscription_inactive.test_block = ProductBlockOneForTestInactive.new(
        subscription_id=list_union_subscription_inactive.subscription_id,
        int_field=3,
        str_field="",
        list_field=[1, 2],
        enum_field=DummyEnum.FOO,
        sub_block=SubBlockOneForTestInactive.new(
            subscription_id=list_union_subscription_inactive.subscription_id, int_field=3, str_field="2"
        ),
        sub_block_2=SubBlockOneForTestInactive.new(
            subscription_id=list_union_subscription_inactive.subscription_id, int_field=3, str_field="2"
        ),
        sub_block_list=[
            sub_one_subscription_1.test_block,
        ],
    )

    new_sub_block_1 = SubBlockOneForTestInactive.new(
        subscription_id=list_union_subscription_inactive.subscription_id, int_field=11, str_field="111"
    )
    new_sub_block_2 = SubBlockOneForTestInactive.new(
        subscription_id=list_union_subscription_inactive.subscription_id, int_field=12, str_field="121"
    )
    list_union_subscription_inactive.list_union_blocks = [new_sub_block_1, new_sub_block_2]
    list_union_subscription_inactive.save()

    list_union_subscription = ProductListUnion.from_other_lifecycle(
        list_union_subscription_inactive, SubscriptionLifecycle.ACTIVE
    )
    list_union_subscription.save()
    return list_union_subscription
