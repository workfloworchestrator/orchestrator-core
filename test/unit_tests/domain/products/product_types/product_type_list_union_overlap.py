from typing import Optional, TypeVar, Union

import pytest

from orchestrator.db import ProductTable, db
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import SubscriptionInstanceList, SubscriptionModel
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product_type_list_union_overlap(test_product_block_one, test_product_sub_block_one):
    ProductBlockOneForTestInactive, ProductBlockOneForTestProvisioning, ProductBlockOneForTest = test_product_block_one
    SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest = test_product_sub_block_one

    T = TypeVar("T", covariant=True)

    class ListOfPorts(SubscriptionInstanceList[T]):
        min_items = 1

    class ProductListUnionInactive(SubscriptionModel, is_base=True):
        test_block: Optional[ProductBlockOneForTestInactive]
        list_union_blocks: ListOfPorts[Union[ProductBlockOneForTestInactive, SubBlockOneForTestInactive]]

    class ProductListUnionProvisioning(ProductListUnionInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_block: ProductBlockOneForTestProvisioning
        list_union_blocks: ListOfPorts[Union[ProductBlockOneForTestProvisioning, SubBlockOneForTestProvisioning]]

    class ProductListUnion(ProductListUnionProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: ProductBlockOneForTest
        list_union_blocks: ListOfPorts[Union[ProductBlockOneForTest, SubBlockOneForTest]]

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
