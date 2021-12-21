from datetime import datetime
from typing import List, Optional, TypeVar, Union
from unittest import mock
from uuid import uuid4

import pytest
import pytz
from pydantic import Field, ValidationError, conlist
from pydantic.main import BaseModel
from pydantic.types import ConstrainedList
from sqlalchemy.orm.exc import NoResultFound

from orchestrator.db import (
    ProductBlockTable,
    ProductTable,
    ResourceTypeTable,
    SubscriptionInstanceRelationTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    db,
)
from orchestrator.db.models import FixedInputTable
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import (
    ProductBlockModel,
    ProductModel,
    SubscriptionInstanceList,
    SubscriptionModel,
    _is_constrained_list_type,
)
from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product_blocks_db():
    resource_type_list = ResourceTypeTable(resource_type="list_field", description="")
    resource_type_int = ResourceTypeTable(resource_type="int_field", description="")
    resource_type_str = ResourceTypeTable(resource_type="str_field", description="")

    product_block = ProductBlockTable(name="BlockForTest", description="Test Block", tag="TEST", status="active")
    product_sub_block = ProductBlockTable(
        name="SubBlockForTest", description="Test Sub Block", tag="TEST", status="active"
    )

    product_block.resource_types = [resource_type_int, resource_type_str, resource_type_list]
    product_sub_block.resource_types = [resource_type_int, resource_type_str]
    product_block.children = [product_sub_block]

    db.session.add(product_block)
    db.session.add(product_sub_block)
    db.session.commit()

    return product_block, product_sub_block


@pytest.fixture
def test_product_blocks_union_db(test_product_blocks_db):
    product_block, product_sub_block = test_product_blocks_db
    resource_type_int = ResourceTypeTable.query.filter(ResourceTypeTable.resource_type == "int_field").one()
    product_union_sub_block = ProductBlockTable(
        name="UnionSubBlockForTest", description="Test Union Sub Block", tag="TEST", status="active"
    )
    product_union_sub_block.resource_types = [resource_type_int]
    db.session.add(product_union_sub_block)
    product_block.children.append(product_union_sub_block)
    db.session.commit()

    return product_block, product_sub_block, product_union_sub_block


@pytest.fixture
def test_product(test_product_blocks_db):
    product = ProductTable(
        name="TestProduct", description="Test ProductTable", product_type="Test", tag="TEST", status="active"
    )

    fixed_input = FixedInputTable(name="test_fixed_input", value="False")

    product_block, product_sub_block = test_product_blocks_db
    product.fixed_inputs = [fixed_input]
    product.product_blocks = [product_block]

    db.session.add(product)
    db.session.commit()

    return product.product_id


@pytest.fixture
def test_union_product(test_product_blocks_db):
    product = ProductTable(
        name="UnionProduct", description="Test Union Product", product_type="Test", tag="Union", status="active"
    )

    product_block, product_sub_block = test_product_blocks_db
    product.product_blocks = [product_block, product_sub_block]
    db.session.add(product)
    db.session.commit()
    return product.product_id


@pytest.fixture
def test_union_sub_product(test_product_blocks_union_db):
    product = ProductTable(
        name="UnionProductSub",
        description="Product with Union sub product_block",
        tag="UnionSub",
        product_type="Test",
        status="active",
    )
    product_block, _, _ = test_product_blocks_union_db
    product.product_blocks = [product_block]
    db.session.add(product)
    db.session.commit()

    return product.product_id


@pytest.fixture
def test_sub_product(test_product_blocks_db):
    product = ProductTable(
        name="SubProduct", description="Test SubProduct", product_type="Test", tag="Sub", status="active"
    )

    product_block, product_sub_block = test_product_blocks_db

    product.product_blocks = [product_sub_block]
    db.session.add(product)
    db.session.commit()
    return product.product_id


@pytest.fixture
def test_product_sub_block():
    class SubBlockForTestInactive(ProductBlockModel, product_block_name="SubBlockForTest"):
        int_field: Optional[int] = None
        str_field: Optional[str] = None

    class SubBlockForTestProvisioning(SubBlockForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        int_field: int
        str_field: Optional[str] = None

    class SubBlockForTest(SubBlockForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        int_field: int
        str_field: str

    return SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest


@pytest.fixture
def test_union_sub_product_block():
    class UnionSubBlockForTestInactive(ProductBlockModel, product_block_name="UnionSubBlockForTest"):
        int_field: Optional[int] = None

    class UnionSubBlockForTestProvisioning(
        UnionSubBlockForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        int_field: int

    class UnionSubBlockForTest(UnionSubBlockForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        int_field: int

    return UnionSubBlockForTestInactive, UnionSubBlockForTestProvisioning, UnionSubBlockForTest


@pytest.fixture
def test_product_block(test_product_sub_block):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block

    class BlockForTestInactive(ProductBlockModel, product_block_name="BlockForTest"):
        sub_block: SubBlockForTestInactive
        sub_block_2: Optional[SubBlockForTestInactive] = None
        sub_block_list: List[SubBlockForTestInactive] = []
        int_field: Optional[int] = None
        str_field: Optional[str] = None
        list_field: List[int] = Field(default_factory=list)

    class BlockForTestProvisioning(BlockForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        sub_block: SubBlockForTestProvisioning
        sub_block_2: SubBlockForTestProvisioning
        sub_block_list: List[SubBlockForTestProvisioning]
        int_field: int
        str_field: Optional[str] = None
        list_field: List[int]

    class BlockForTest(BlockForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        sub_block: SubBlockForTest
        sub_block_2: SubBlockForTest
        sub_block_list: List[SubBlockForTest]
        int_field: int
        str_field: str
        list_field: List[int]

    return BlockForTestInactive, BlockForTestProvisioning, BlockForTest


@pytest.fixture
def test_product_block_with_union(test_product_sub_block, test_union_sub_product_block):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block
    UnionSubBlockForTestInactive, UnionSubBlockForTestProvisioning, UnionSubBlockForTest = test_union_sub_product_block

    class BlockForTestInactive(ProductBlockModel, product_block_name="BlockForTest"):
        union_block: Optional[Union[SubBlockForTestInactive, UnionSubBlockForTestInactive]] = None
        int_field: Optional[int] = None
        str_field: Optional[str] = None
        list_field: List[int] = Field(default_factory=list)

    class BlockForTestProvisioning(BlockForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        union_block: Union[SubBlockForTestProvisioning, UnionSubBlockForTestProvisioning]
        int_field: int
        str_field: Optional[str] = None
        list_field: List[int]

    class BlockForTest(BlockForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        union_block: Union[SubBlockForTest, UnionSubBlockForTest]
        int_field: int
        str_field: str
        list_field: List[int]

    return BlockForTestInactive, BlockForTestProvisioning, BlockForTest


@pytest.fixture
def test_product_with_union_sub_product_block(test_product_block_with_union):
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block_with_union

    class UnionProductSubInactive(SubscriptionModel, is_base=True):
        test_block: Optional[BlockForTestInactive]

    class UnionProductSubProvisioning(UnionProductSubInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_block: BlockForTestProvisioning

    class UnionProductSub(UnionProductSubProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: BlockForTest

    SUBSCRIPTION_MODEL_REGISTRY["UnionProductSub"] = UnionProductSub
    yield UnionProductSubInactive, UnionProductSubProvisioning, UnionProductSub
    del SUBSCRIPTION_MODEL_REGISTRY["UnionProductSub"]


@pytest.fixture
def test_union_type_product(test_product_sub_block, test_product_block):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block

    class UnionProductInactive(SubscriptionModel, is_base=True):
        test_block: Optional[BlockForTestInactive]
        union_block: Optional[Union[SubBlockForTestInactive, BlockForTestInactive]]

    class UnionProductProvisioning(UnionProductInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_block: BlockForTestProvisioning
        union_block: Union[SubBlockForTestProvisioning, BlockForTestProvisioning]

    class UnionProduct(UnionProductProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: BlockForTest
        union_block: Union[SubBlockForTest, BlockForTest]

    SUBSCRIPTION_MODEL_REGISTRY["UnionProduct"] = UnionProduct
    yield UnionProductInactive, UnionProductProvisioning, UnionProduct
    del SUBSCRIPTION_MODEL_REGISTRY["UnionProduct"]


@pytest.fixture
def test_sub_type_product(test_product_sub_block):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block

    class SubProductInactive(SubscriptionModel, is_base=True):
        test_block: Optional[SubBlockForTestInactive]

    class SubProductProvisioning(SubProductInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_block: SubBlockForTestProvisioning

    class SubProduct(SubProductProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: SubBlockForTest

    SUBSCRIPTION_MODEL_REGISTRY["SubProduct"] = SubProduct
    yield SubProductInactive, SubProductProvisioning, SubProduct
    del SUBSCRIPTION_MODEL_REGISTRY["SubProduct"]


@pytest.fixture
def test_product_type(test_product_block):
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block

    class ProductTypeForTestInactive(SubscriptionModel, is_base=True):
        test_fixed_input: bool
        block: BlockForTestInactive

    class ProductTypeForTestProvisioning(ProductTypeForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        test_fixed_input: bool
        block: BlockForTestProvisioning

    class ProductTypeForTest(ProductTypeForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: BlockForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProduct"] = ProductTypeForTest

    yield ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest

    del SUBSCRIPTION_MODEL_REGISTRY["TestProduct"]


@pytest.fixture
def test_product_model(test_product):
    return ProductModel(
        product_id=test_product,
        name="TestProduct",
        description="Test ProductTable",
        product_type="Test",
        tag="TEST",
        status=ProductLifecycle.ACTIVE,
    )


def test_product_block_metadata(test_product_block, test_product, test_product_blocks_db):
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block

    subscription_id = uuid4()
    BlockForTestInactive.new(
        subscription_id=subscription_id
    )  # Need at least one instance since we lazy load this stuff

    product_block, product_sub_block = test_product_blocks_db

    assert BlockForTestInactive.name == "BlockForTest"
    assert BlockForTestInactive.description == "Test Block"
    assert BlockForTestInactive.product_block_id == product_block.product_block_id
    assert BlockForTestInactive.tag == "TEST"


def test_lifecycle(test_product_model, test_product_type, test_product_block):
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type
    subscription_id = uuid4()

    # Test create with wrong lifecycle, we can create
    with pytest.raises(ValueError, match=r"is not valid for status active"):
        ProductTypeForTestInactive(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=subscription_id,
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            block=BlockForTestInactive.new(subscription_id),
            status=SubscriptionLifecycle.ACTIVE,
            test_fixed_input=False,
        )

    # Works with right lifecycle
    product_type = ProductTypeForTestInactive(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTestInactive.new(subscription_id),
        status=SubscriptionLifecycle.INITIAL,
        test_fixed_input=False,
    )

    assert product_type.status == SubscriptionLifecycle.INITIAL


def test_lifecycle_specific(test_product_model, test_product_type, test_product_block, test_product_sub_block):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type
    subscription_id = uuid4()

    # Works with less contrained lifecycle
    product_type = ProductTypeForTest(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTest.new(
            subscription_id=subscription_id,
            int_field=3,
            str_field="",
            list_field=[1],
            sub_block=SubBlockForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.INITIAL,
        test_fixed_input=False,
    )

    assert product_type.status == SubscriptionLifecycle.INITIAL

    # Works with right lifecycle
    product_type = ProductTypeForTest(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTest.new(
            subscription_id=subscription_id,
            int_field=3,
            str_field="",
            list_field=[1],
            sub_block=SubBlockForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.ACTIVE,
        test_fixed_input=False,
    )

    assert product_type.status == SubscriptionLifecycle.ACTIVE

    # Does not work with more constrained lifecycle
    with pytest.raises(ValueError, match=r"is not valid for status active"):
        ProductTypeForTestProvisioning(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=subscription_id,
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            block=BlockForTestProvisioning.new(
                subscription_id=subscription_id,
                int_field=3,
                list_field=[1],
                sub_block=SubBlockForTestProvisioning.new(subscription_id=subscription_id, int_field=3),
                sub_block_2=SubBlockForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            ),
            status=SubscriptionLifecycle.ACTIVE,
            test_fixed_input=False,
        )

    # Works with right lifecycle
    product_type = ProductTypeForTestProvisioning(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTestProvisioning.new(
            subscription_id=subscription_id,
            int_field=3,
            list_field=[1],
            sub_block=SubBlockForTestProvisioning.new(subscription_id=subscription_id, int_field=3),
            sub_block_2=SubBlockForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.PROVISIONING,
        test_fixed_input=False,
    )
    assert product_type.status == SubscriptionLifecycle.PROVISIONING


def test_product_blocks_per_lifecycle(
    test_product_model, test_product_type, test_product_block, test_product_sub_block
):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type
    subscription_id = uuid4()

    ProductTypeForTestInactive(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTest.new(
            subscription_id=subscription_id,
            int_field=3,
            str_field="",
            list_field=[1],
            sub_block=SubBlockForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.INITIAL,
        test_fixed_input=False,
    )

    ProductTypeForTestInactive(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTestInactive.new(subscription_id=subscription_id, int_field=3),
        status=SubscriptionLifecycle.INITIAL,
        test_fixed_input=False,
    )

    ProductTypeForTestProvisioning(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTest.new(
            subscription_id=subscription_id,
            int_field=3,
            str_field="",
            list_field=[1],
            sub_block=SubBlockForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.PROVISIONING,
        test_fixed_input=False,
    )

    ProductTypeForTest(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTest.new(
            subscription_id=subscription_id,
            int_field=3,
            str_field="",
            list_field=[1],
            sub_block=SubBlockForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.ACTIVE,
        test_fixed_input=False,
    )

    ProductTypeForTest(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTest.new(
            subscription_id=subscription_id,
            int_field=3,
            str_field="",
            list_field=[1],
            sub_block=SubBlockForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.INITIAL,
        test_fixed_input=False,
    )

    with pytest.raises(
        ValidationError,
        match=r"2 validation errors for SubBlockForTest\nint_field\n  field required .+\nstr_field\n  field required .+",
    ):
        ProductTypeForTest(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=subscription_id,
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            block=BlockForTest.new(subscription_id=subscription_id),
            status=SubscriptionLifecycle.ACTIVE,
            test_fixed_input=False,
        )

    with pytest.raises(ValidationError, match=r"5 validation errors for ProductTypeForTest"):
        ProductTypeForTest(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=subscription_id,
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            block=BlockForTestInactive.new(subscription_id=subscription_id),
            status=SubscriptionLifecycle.ACTIVE,
            test_fixed_input=False,
        )

    with pytest.raises(ValidationError, match=r"1 validation error for ProductTypeForTest\nblock\n  field required .+"):
        ProductTypeForTest(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=subscription_id,
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            status=SubscriptionLifecycle.INITIAL,
            test_fixed_input=False,
        )

    with pytest.raises(ValidationError, match=r"1 validation error for ProductTypeForTest\nblock\n  field required .+"):
        ProductTypeForTest(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=subscription_id,
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            status=SubscriptionLifecycle.ACTIVE,
            test_fixed_input=False,
        )


def test_change_lifecycle(test_product, test_product_type, test_product_block, test_product_sub_block):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    product_type = ProductTypeForTestInactive.from_product_id(
        test_product,
        uuid4(),
    )
    product_type.block = BlockForTestInactive.new(
        subscription_id=product_type.subscription_id,
        sub_block_2=SubBlockForTestInactive.new(subscription_id=product_type.subscription_id),
    )

    # Does not work if constraints are not met
    with pytest.raises(ValidationError, match=r"int_field\n  none is not an allowed value"):
        product_type = SubscriptionModel.from_other_lifecycle(product_type, SubscriptionLifecycle.ACTIVE)
    with pytest.raises(ValidationError, match=r"int_field\n  none is not an allowed value"):
        product_type = SubscriptionModel.from_other_lifecycle(product_type, SubscriptionLifecycle.PROVISIONING)

    # Set first value
    product_type.block.int_field = 3
    product_type.block.sub_block.int_field = 3
    product_type.block.sub_block_2.int_field = 3
    product_type.block.sub_block_list = [SubBlockForTestInactive.new(subscription_id=product_type.subscription_id)]
    product_type.block.sub_block_list[0].int_field = 4
    product_type.block.list_field = [1]

    # Does not work if constraints are not met
    with pytest.raises(ValidationError, match=r"str_field\n  none is not an allowed value"):
        product_type = SubscriptionModel.from_other_lifecycle(product_type, SubscriptionLifecycle.ACTIVE)

    # works with correct data
    product_type = SubscriptionModel.from_other_lifecycle(product_type, SubscriptionLifecycle.PROVISIONING)
    assert product_type.status == SubscriptionLifecycle.PROVISIONING
    assert product_type.block.str_field is None

    product_type.block.str_field = "A"
    product_type.block.sub_block.str_field = "B"
    product_type.block.sub_block_2.str_field = "C"
    product_type.block.sub_block_list[0].str_field = "D"

    # works with correct data
    product_type_new = SubscriptionModel.from_other_lifecycle(product_type, SubscriptionLifecycle.ACTIVE)
    assert product_type_new.status == SubscriptionLifecycle.ACTIVE
    expected_dict = product_type.dict()
    expected_dict["status"] = SubscriptionLifecycle.ACTIVE
    expected_dict["start_date"] = mock.ANY
    assert product_type_new.dict() == expected_dict
    assert isinstance(product_type_new.start_date, datetime)


def test_save_load(test_product_model, test_product_type, test_product_block, test_product_sub_block):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    customer_id = uuid4()

    model = ProductTypeForTestInactive.from_product_id(
        product_id=test_product_model.product_id,
        customer_id=customer_id,
        insync=True,
        description="Desc",
        start_date=datetime(2021, 1, 1, 1, 1, 1, tzinfo=pytz.utc),
        end_date=datetime(2021, 1, 1, 1, 1, 2, tzinfo=pytz.utc),
        note="Note",
        status=SubscriptionLifecycle.INITIAL,
    )

    # Set one value and make sure its saved
    model.block.str_field = "A"

    model.save()
    db.session.commit()

    assert (
        SubscriptionInstanceValueTable.query.join(SubscriptionInstanceValueTable.subscription_instance)
        .filter(SubscriptionInstanceTable.subscription_id == model.subscription_id)
        .count()
        == 1
    )

    assert model.dict() == {
        "block": {
            "int_field": None,
            "label": None,
            "list_field": [],
            "name": "BlockForTest",
            "str_field": "A",
            "sub_block": {
                "int_field": None,
                "label": None,
                "name": "SubBlockForTest",
                "str_field": None,
                "subscription_instance_id": mock.ANY,
                "owner_subscription_id": mock.ANY,
            },
            "sub_block_2": None,
            "sub_block_list": [],
            "owner_subscription_id": mock.ANY,
            "subscription_instance_id": mock.ANY,
        },
        "customer_id": customer_id,
        "description": "Desc",
        "end_date": datetime(2021, 1, 1, 1, 1, 2, tzinfo=pytz.utc),
        "insync": True,
        "note": "Note",
        "product": {
            "description": "Test ProductTable",
            "name": "TestProduct",
            "product_id": test_product_model.product_id,
            "product_type": "Test",
            "status": ProductLifecycle.ACTIVE,
            "tag": "TEST",
        },
        "start_date": datetime(2021, 1, 1, 1, 1, 1, tzinfo=pytz.utc),
        "status": SubscriptionLifecycle.INITIAL,
        "subscription_id": mock.ANY,
        "test_fixed_input": False,
    }

    # Set first value
    model.block.int_field = 3
    model.block.sub_block.int_field = 3
    model.block.sub_block_2 = SubBlockForTestInactive.new(subscription_id=model.subscription_id)
    model.block.sub_block_2.int_field = 3
    model.block.list_field = [1]
    model.block.sub_block.str_field = "B"
    model.block.sub_block_2.str_field = "C"

    # works with correct data
    model = SubscriptionModel.from_other_lifecycle(model, SubscriptionLifecycle.ACTIVE)

    model.save()
    db.session.commit()

    new_model = ProductTypeForTest.from_subscription(model.subscription_id)
    assert model.dict() == new_model.dict()

    # Second save also works as expected
    new_model.save()
    db.session.commit()

    latest_model = ProductTypeForTest.from_subscription(model.subscription_id)
    assert new_model.dict() == latest_model.dict()

    # Loading blocks also works
    block = BlockForTest.from_db(model.block.subscription_instance_id)
    assert block.dict() == model.block.dict()


def test_update_constrained_lists(test_product, test_product_block):
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block

    class TestConListProductType(SubscriptionModel, is_base=True):
        saps: conlist(BlockForTestInactive, min_items=1, max_items=4)

    # Creates
    ip = TestConListProductType.from_product_id(product_id=test_product, customer_id=uuid4())
    ip.save()

    sap = BlockForTestInactive.new(subscription_id=ip.subscription_id, int_field=3, str_field="")

    # Set new saps, removes old one
    ip.saps = [sap]

    ip.save()

    ip2 = TestConListProductType.from_subscription(ip.subscription_id)

    # Old default saps should not be saved
    assert ip.dict() == ip2.dict()

    # Test constraint
    with pytest.raises(ValidationError):
        ip.saps = []


def test_update_lists(test_product, test_product_block):
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block

    class TestListProductType(SubscriptionModel, is_base=True):
        saps: List[BlockForTestInactive]

    # Creates
    ip = TestListProductType.from_product_id(product_id=test_product, customer_id=uuid4())
    ip.save()

    sap = BlockForTestInactive.new(subscription_id=ip.subscription_id, int_field=3, str_field="")

    # Set new saps
    ip.saps = [sap]

    ip.save()

    ip2 = TestListProductType.from_subscription(ip.subscription_id)

    # Old default saps should not be saved
    assert ip.dict() == ip2.dict()


def test_update_optional(test_product, test_product_block):
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block

    class TestListProductType(SubscriptionModel, is_base=True):
        sap: Optional[BlockForTestInactive] = None

    # Creates
    ip = TestListProductType.from_product_id(product_id=test_product, customer_id=uuid4())
    ip.save()

    sap = BlockForTestInactive.new(subscription_id=ip.subscription_id, int_field=3, str_field="")

    # Set new sap
    ip.sap = sap

    ip.save()

    ip2 = TestListProductType.from_subscription(ip.subscription_id)

    # Old default saps should not be saved
    assert ip.dict() == ip2.dict()


def test_generic_from_subscription(test_product, test_product_type):
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    ip = ProductTypeForTestInactive.from_product_id(product_id=test_product, customer_id=uuid4())
    ip.save()

    model = SubscriptionModel.from_subscription(ip.subscription_id)

    assert isinstance(model, ProductTypeForTestInactive)


def test_label_is_saved(test_product, test_product_type):
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    test_model = ProductTypeForTestInactive.from_product_id(test_product, uuid4())
    test_model.block.label = "My label"
    test_model.save()
    db.session.commit()
    instance_in_db = SubscriptionInstanceTable.query.get(test_model.block.subscription_instance_id)
    assert instance_in_db.label == "My label"


def test_domain_model_attrs_saving_loading(test_product, test_product_type, test_product_sub_block):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    test_model = ProductTypeForTestInactive.from_product_id(product_id=test_product, customer_id=uuid4())
    test_model.block.sub_block_2 = SubBlockForTestInactive.new(subscription_id=test_model.subscription_id)
    test_model.block.sub_block_list = [SubBlockForTestInactive.new(subscription_id=test_model.subscription_id)]
    test_model.save()
    db.session.commit()

    relation = SubscriptionInstanceRelationTable.query.filter(
        SubscriptionInstanceRelationTable.child_id == test_model.block.sub_block.subscription_instance_id
    ).one()
    assert relation.domain_model_attr == "sub_block"
    relation = SubscriptionInstanceRelationTable.query.filter(
        SubscriptionInstanceRelationTable.child_id == test_model.block.sub_block_2.subscription_instance_id
    ).one()
    assert relation.domain_model_attr == "sub_block_2"
    relation = SubscriptionInstanceRelationTable.query.filter(
        SubscriptionInstanceRelationTable.child_id == test_model.block.sub_block_list[0].subscription_instance_id
    ).one()
    assert relation.domain_model_attr == "sub_block_list"
    test_model_2 = ProductTypeForTestInactive.from_subscription(test_model.subscription_id)
    assert test_model == test_model_2


def test_removal_of_domain_attrs(test_product, test_product_type, test_product_sub_block):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    test_model = ProductTypeForTestInactive.from_product_id(product_id=test_product, customer_id=uuid4())
    test_model.block.sub_block_2 = SubBlockForTestInactive.new(subscription_id=test_model.subscription_id)

    test_model.save()
    db.session.commit()
    relation = SubscriptionInstanceRelationTable.query.filter(
        SubscriptionInstanceRelationTable.child_id == test_model.block.sub_block.subscription_instance_id
    ).one()
    relation.domain_model_attr = None
    db.session.commit()
    with pytest.raises(ValueError, match=r"Expected exactly one item in iterable, but got"):
        ProductTypeForTestInactive.from_subscription(test_model.subscription_id)


def test_simple_model_with_no_attrs(generic_subscription_1, generic_product_type_1):
    GenericProductOneInactive, GenericProductOne = generic_product_type_1
    model = GenericProductOne.from_subscription(subscription_id=generic_subscription_1)
    with pytest.raises(NoResultFound):
        SubscriptionInstanceRelationTable.query.filter(
            SubscriptionInstanceRelationTable.child_id == model.pb_1.subscription_instance_id
        ).one()


def test_abstract_super_block(test_product, test_product_type, test_product_blocks_db):
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    class AbstractBlockForTestInactive(ProductBlockModel):
        str_field: Optional[str] = None
        list_field: List[int] = Field(default_factory=list)

    class AbstractBlockForTestProvisioning(
        AbstractBlockForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        str_field: Optional[str] = None
        list_field: List[int]

    class AbstractBlockForTest(AbstractBlockForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        str_field: str
        list_field: List[int]

    class BlockForTestInactive(AbstractBlockForTestInactive, product_block_name="BlockForTest"):
        str_field: Optional[str] = None
        list_field: List[int] = Field(default_factory=list)
        int_field: Optional[int] = None

    class BlockForTestProvisioning(
        BlockForTestInactive, AbstractBlockForTestProvisioning, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        str_field: Optional[str] = None
        list_field: List[int]
        int_field: int

    class BlockForTest(BlockForTestProvisioning, AbstractBlockForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        str_field: str
        list_field: List[int]
        int_field: int

    class AbstractProductTypeForTestInactive(SubscriptionModel):
        block: AbstractBlockForTestInactive

    class AbstractProductTypeForTestProvisioning(AbstractProductTypeForTestInactive):
        block: AbstractBlockForTestProvisioning

    class AbstractProductTypeForTest(AbstractProductTypeForTestProvisioning):
        block: AbstractBlockForTest

    class ProductTypeForTestInactive(AbstractProductTypeForTestInactive, is_base=True):
        block: BlockForTestInactive

    class ProductTypeForTestProvisioning(
        ProductTypeForTestInactive,
        AbstractProductTypeForTestProvisioning,
        lifecycle=[SubscriptionLifecycle.PROVISIONING],
    ):
        block: BlockForTestProvisioning

    class ProductTypeForTest(
        ProductTypeForTestProvisioning, AbstractProductTypeForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        block: BlockForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProduct"] = ProductTypeForTest

    test_model = ProductTypeForTestInactive.from_product_id(product_id=test_product, customer_id=uuid4())
    test_model.block = BlockForTestInactive.new(subscription_id=test_model.subscription_id)

    product_block, product_sub_block = test_product_blocks_db

    # Check metadata
    with pytest.raises(ValueError, match=r"Cannot create instance of abstract class. Use one of {'BlockForTest'}"):
        AbstractBlockForTestInactive.new(subscription_id=test_model.subscription_id)
    assert AbstractBlockForTestInactive.name is None
    assert not hasattr(AbstractBlockForTestInactive, "description")
    assert not hasattr(AbstractBlockForTestInactive, "product_block_id")
    assert not hasattr(AbstractBlockForTestInactive, "tag")
    assert BlockForTestInactive.name == "BlockForTest"
    assert BlockForTestInactive.description == "Test Block"
    assert BlockForTestInactive.product_block_id == product_block.product_block_id
    assert BlockForTestInactive.tag == "TEST"

    test_model.save()
    db.session.commit()

    test_model = AbstractProductTypeForTestInactive.from_subscription(test_model.subscription_id)
    assert isinstance(test_model, ProductTypeForTestInactive)
    assert isinstance(test_model.block, BlockForTestInactive)

    test_model = ProductTypeForTestInactive.from_subscription(test_model.subscription_id)
    assert isinstance(test_model.block, BlockForTestInactive)

    test_model.block.int_field = 1
    test_model.block.str_field = "bla"
    test_model.block.list_field = [1]

    test_model = SubscriptionModel.from_other_lifecycle(test_model, SubscriptionLifecycle.ACTIVE)
    test_model.save()
    assert isinstance(test_model.block, BlockForTest)

    test_model = AbstractProductTypeForTest.from_subscription(test_model.subscription_id)
    assert isinstance(test_model.block, BlockForTest)

    test_model = ProductTypeForTest.from_subscription(test_model.subscription_id)
    assert isinstance(test_model.block, BlockForTest)

    block = AbstractBlockForTest.from_db(test_model.block.subscription_instance_id)
    assert block.dict() == test_model.block.dict()
    assert isinstance(block, BlockForTest)

    block = BlockForTest.from_db(test_model.block.subscription_instance_id)
    assert block.dict() == test_model.block.dict()
    assert isinstance(block, BlockForTest)


def test_subscription_instance_list():
    T = TypeVar("T")

    class Max2List(SubscriptionInstanceList[T]):
        max_items = 2

    # Also check generic subclass
    class ConList(Max2List[T]):
        min_items = 1

    class Model(BaseModel):
        list_field: ConList[int]

    with pytest.raises(ValidationError):
        Model(list_field=["a"])

    Model(list_field=[1])


def test_is_constrained_list_type():
    class ListType(ConstrainedList):
        min_items = 1

    assert _is_constrained_list_type(ListType) is True
    assert _is_constrained_list_type(SubscriptionInstanceList[int]) is True
    assert _is_constrained_list_type(Optional[int]) is False
    assert _is_constrained_list_type(List[int]) is False


def test_diff_in_db(test_product, test_product_type):
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    assert ProductTypeForTestInactive.diff_product_in_database(test_product) == {}

    class Wrong(SubscriptionModel):
        pass

    assert (
        Wrong.diff_product_in_database(test_product)
        == {
            "TestProduct": {
                "missing_fixed_inputs_in_model": {"test_fixed_input"},
                "missing_product_blocks_in_model": {"BlockForTest"},
            }
        }
        != {
            "TestProduct": {
                "missing_in_children": {"BlockForTest": {"missing_product_blocks_in_db": {"SubBlockForTest"}}},
                "missing_product_blocks_in_model": {"SubBlockForTest"},
            }
        }
    )


def test_diff_in_db_missing_in_db(test_product_type):
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    product = ProductTable(
        name="TestProductEmpty", description="Test ProductTable", product_type="Test", tag="TEST", status="active"
    )

    db.session.add(product)
    db.session.commit()

    assert ProductTypeForTestInactive.diff_product_in_database(product.product_id) == {
        "TestProductEmpty": {
            "missing_fixed_inputs_in_db": {"test_fixed_input"},
            "missing_in_children": {
                "BlockForTest": {
                    "missing_product_blocks_in_db": {"SubBlockForTest"},
                    "missing_resource_types_in_db": {"int_field", "list_field", "str_field"},
                },
                "SubBlockForTest": {"missing_resource_types_in_db": {"int_field", "str_field"}},
            },
            "missing_product_blocks_in_db": {"BlockForTest"},
        }
    }


def test_from_other_lifecycle_abstract(test_product):
    class AbstractBlockForTestInactive(ProductBlockModel, product_block_name="BlockForTest"):
        str_field: Optional[str] = None
        list_field: List[int] = Field(default_factory=list)

    class AbstractBlockForTestProvisioning(
        AbstractBlockForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        str_field: Optional[str] = None
        list_field: List[int]

    class AbstractBlockForTest(AbstractBlockForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        str_field: str
        list_field: List[int]

    class BlockForTestInactive(AbstractBlockForTestInactive, product_block_name="BlockForTest"):
        str_field: Optional[str] = None
        list_field: List[int] = Field(default_factory=list)
        int_field: Optional[int] = None

    class BlockForTestProvisioning(
        BlockForTestInactive, AbstractBlockForTestProvisioning, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        str_field: Optional[str] = None
        list_field: List[int]
        int_field: int

    class BlockForTest(BlockForTestProvisioning, AbstractBlockForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        str_field: str
        list_field: List[int]
        int_field: int

    block = BlockForTestInactive.new(subscription_id=uuid4())
    assert isinstance(block, BlockForTestInactive)

    block.int_field = 1
    block.str_field = "bla"
    block.list_field = [1]

    active_block = BlockForTest._from_other_lifecycle(block, SubscriptionLifecycle.ACTIVE, uuid4())

    assert isinstance(active_block, AbstractBlockForTest)
    assert isinstance(active_block, BlockForTest)
    assert active_block.db_model == block.db_model


def test_from_other_lifecycle_sub(test_product, test_product_block, test_product_sub_block):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block
    subscription_id = uuid4()

    block = BlockForTestInactive.new(subscription_id=subscription_id, int_field=1, str_field="bla", list_field=[1])
    block.sub_block = SubBlockForTestInactive.new(subscription_id=subscription_id, int_field=1, str_field="bla")
    block.sub_block_2 = SubBlockForTestInactive.new(subscription_id=subscription_id, int_field=1, str_field="bla")
    block.sub_block_list = [SubBlockForTestInactive.new(subscription_id=subscription_id, int_field=1, str_field="bla")]

    assert isinstance(block, BlockForTestInactive)

    active_block = BlockForTest._from_other_lifecycle(block, SubscriptionLifecycle.ACTIVE, uuid4())

    assert isinstance(active_block, BlockForTest)
    assert isinstance(active_block.sub_block, SubBlockForTest)
    assert isinstance(active_block.sub_block_2, SubBlockForTest)
    assert isinstance(active_block.sub_block_list[0], SubBlockForTest)
    assert active_block.db_model == block.db_model
    assert active_block.sub_block.db_model == block.sub_block.db_model
    assert active_block.sub_block_2.db_model == block.sub_block_2.db_model
    assert active_block.sub_block_list[0].db_model == block.sub_block_list[0].db_model


def test_prodcut_model_with_union_type_directly_below(
    test_union_product,
    test_union_type_product,
    test_sub_product,
    test_sub_type_product,
    test_product_sub_block,
    test_product_block,
):
    UnionProductInactive, UnionProductProvisioning, UnionProduct = test_union_type_product
    SubProductInactive, SubProductProvisioning, SubProduct = test_sub_type_product
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block

    sub_subscription_inactive = SubProductInactive.from_product_id(product_id=test_sub_product, customer_id=uuid4())
    sub_subscription_inactive.test_block = SubBlockForTestInactive.new(
        subscription_id=sub_subscription_inactive.subscription_id, int_field=1, str_field="blah"
    )
    sub_subscription_inactive.save()
    sub_subscription_active = SubscriptionModel.from_other_lifecycle(
        sub_subscription_inactive, SubscriptionLifecycle.ACTIVE
    )
    sub_subscription_active.save()

    union_subscription_inactive = UnionProductInactive.from_product_id(
        product_id=test_union_product, customer_id=uuid4()
    )

    union_subscription_inactive.test_block = BlockForTestInactive.new(
        subscription_id=union_subscription_inactive.subscription_id,
        int_field=3,
        str_field="",
        list_field=[1],
        sub_block=SubBlockForTestInactive.new(
            subscription_id=union_subscription_inactive.subscription_id, int_field=3, str_field=""
        ),
        sub_block_2=SubBlockForTestInactive.new(
            subscription_id=union_subscription_inactive.subscription_id, int_field=3, str_field=""
        ),
    )

    with pytest.raises(AttributeError):
        SubscriptionModel.from_other_lifecycle(union_subscription_inactive, SubscriptionLifecycle.ACTIVE)

    new_sub_block = SubBlockForTest.new(
        subscription_id=union_subscription_inactive.subscription_id, int_field=1, str_field="2"
    )
    union_subscription_inactive.union_block = new_sub_block
    union_subscription_inactive.save()

    assert union_subscription_inactive.diff_product_in_database(union_subscription_inactive.product.product_id) == {}
    union_subscription = SubscriptionModel.from_other_lifecycle(
        union_subscription_inactive, SubscriptionLifecycle.ACTIVE
    )

    union_subscription.union_block = sub_subscription_active.test_block

    with pytest.raises(ValueError) as exc:
        union_subscription.save()
        assert (
            str(exc)
            == "Attempting to save a Foreign `Subscription Instance` directly below a subscription. This is not allowed."
        )


def test_union_productblock_as_sub(
    test_product_with_union_sub_product_block,
    test_product_block_with_union,
    test_sub_type_product,
    test_product_sub_block,
    test_sub_product,
    test_union_sub_product,
):
    UnionProductSubInactive, UnionProductSubProvisioning, UnionProductSub = test_product_with_union_sub_product_block
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block_with_union
    SubProductInactive, SubProductProvisioning, SubProduct = test_sub_type_product
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block

    sub_subscription_inactive = SubProductInactive.from_product_id(product_id=test_sub_product, customer_id=uuid4())
    sub_subscription_inactive.test_block = SubBlockForTestInactive.new(
        subscription_id=sub_subscription_inactive.subscription_id, int_field=1, str_field="blah"
    )
    sub_subscription_inactive.save()
    sub_subscription_active = SubscriptionModel.from_other_lifecycle(
        sub_subscription_inactive, SubscriptionLifecycle.ACTIVE
    )
    sub_subscription_active.save()

    union_subscription_inactive = UnionProductSubInactive.from_product_id(
        product_id=test_union_sub_product, customer_id=uuid4()
    )
    union_subscription_inactive.test_block = BlockForTestInactive.new(
        subscription_id=union_subscription_inactive.subscription_id
    )
    union_subscription_inactive.save()

    union_subscription_inactive.test_block.int_field = 1
    union_subscription_inactive.test_block.str_field = "blah"
    union_subscription_inactive.test_block.union_block = sub_subscription_active.test_block

    union_subscription_inactive.test_block.list_field = [2]

    union_subscription = SubscriptionModel.from_other_lifecycle(
        union_subscription_inactive, status=SubscriptionLifecycle.ACTIVE
    )
    union_subscription.save()

    # This needs to happen in the test due to the fact it is using cached objects.
    db.session.commit()
    assert union_subscription.diff_product_in_database(test_union_sub_product) == {}

    union_subscription_from_database = SubscriptionModel.from_subscription(union_subscription.subscription_id)

    assert type(union_subscription_from_database) == type(union_subscription)
    assert union_subscription_from_database.test_block.int_field == union_subscription.test_block.int_field
    assert union_subscription_from_database.test_block.str_field == union_subscription.test_block.str_field
    assert (
        union_subscription_from_database.test_block.union_block.subscription_instance_id
        == sub_subscription_active.test_block.subscription_instance_id
    )

    sub_subscription_terminated = SubscriptionModel.from_other_lifecycle(
        sub_subscription_active, SubscriptionLifecycle.TERMINATED
    )

    # Do not allow subscriptions that have a parent make an unsafe transition.
    with pytest.raises(ValueError):
        sub_subscription_terminated.save()
