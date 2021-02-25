from typing import List, Optional
from uuid import uuid4

import pytest
from pydantic import ValidationError, conlist
from sqlalchemy.orm.exc import NoResultFound

from orchestrator.db import (
    ProductBlockTable,
    ProductTable,
    ResourceTypeTable,
    SubscriptionInstanceRelationTable,
    SubscriptionInstanceTable,
    db,
)
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import ProductBlockModel, ProductModel, SubscriptionModel
from orchestrator.domain.lifecycle import ProductLifecycle, change_lifecycle
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def test_product():
    resource_type_int = ResourceTypeTable(resource_type="int_field", description="")
    resource_type_str = ResourceTypeTable(resource_type="str_field", description="")
    product_block = ProductBlockTable(name="BlockForTest", description="Test Block", tag="TEST", status="active")
    product_sub_block = ProductBlockTable(
        name="SubBlockForTest", description="Test Sub Block", tag="TEST", status="active"
    )
    product = ProductTable(
        name="TestProduct", description="Test ProductTable", product_type="Test", tag="TEST", status="active"
    )

    product_block.resource_types = [resource_type_int, resource_type_str]
    product_sub_block.resource_types = [resource_type_int, resource_type_str]
    product.product_blocks = [product_block, product_sub_block]

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
def test_product_block(test_product_sub_block):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block

    class BlockForTestInactive(ProductBlockModel, product_block_name="BlockForTest"):
        sub_block: SubBlockForTestInactive
        sub_block_2: SubBlockForTestInactive
        int_field: Optional[int] = None
        str_field: Optional[str] = None

    class BlockForTestProvisioning(BlockForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        sub_block: SubBlockForTestProvisioning
        sub_block_2: SubBlockForTestProvisioning
        int_field: int
        str_field: Optional[str] = None

    class BlockForTest(BlockForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        sub_block: SubBlockForTest
        sub_block_2: SubBlockForTest
        int_field: int
        str_field: str

    return BlockForTestInactive, BlockForTestProvisioning, BlockForTest


@pytest.fixture
def test_product_type(test_product_block):
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block

    class ProductTypeForTestInactive(SubscriptionModel, is_base=True):
        block: BlockForTestInactive

    class ProductTypeForTestProvisioning(ProductTypeForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        block: BlockForTestProvisioning

    class ProductTypeForTest(ProductTypeForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
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


def test_lifecycle(test_product_model, test_product_type, test_product_block):
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    # Test create with wrong lifecycle, we can create
    with pytest.raises(ValueError, match=r"is not valid for status active"):
        ProductTypeForTestInactive(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=uuid4(),
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            block=BlockForTestInactive.new(),
            status=SubscriptionLifecycle.ACTIVE,
        )

    # Works with right lifecycle
    product_type = ProductTypeForTestInactive(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=uuid4(),
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTestInactive.new(),
        status=SubscriptionLifecycle.INITIAL,
    )

    assert product_type.status == SubscriptionLifecycle.INITIAL


def test_lifecycle_specific(test_product_model, test_product_type, test_product_block, test_product_sub_block):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    # Works with less contrained lifecycle
    product_type = ProductTypeForTest(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=uuid4(),
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTest.new(
            int_field=3,
            str_field="",
            sub_block=SubBlockForTest.new(int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.INITIAL,
    )

    assert product_type.status == SubscriptionLifecycle.INITIAL

    # Works with right lifecycle
    product_type = ProductTypeForTest(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=uuid4(),
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTest.new(
            int_field=3,
            str_field="",
            sub_block=SubBlockForTest.new(int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.ACTIVE,
    )

    assert product_type.status == SubscriptionLifecycle.ACTIVE

    # Does not work with more constrained lifecycle
    with pytest.raises(ValueError, match=r"is not valid for status active"):
        ProductTypeForTestProvisioning(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=uuid4(),
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            block=BlockForTestProvisioning.new(
                int_field=3,
                sub_block=SubBlockForTestProvisioning.new(int_field=3),
                sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
            ),
            status=SubscriptionLifecycle.ACTIVE,
        )

    # Works with right lifecycle
    product_type = ProductTypeForTestProvisioning(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=uuid4(),
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTestProvisioning.new(
            int_field=3,
            sub_block=SubBlockForTestProvisioning.new(int_field=3),
            sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.PROVISIONING,
    )
    assert product_type.status == SubscriptionLifecycle.PROVISIONING


def test_product_blocks_per_lifecycle(
    test_product_model, test_product_type, test_product_block, test_product_sub_block
):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    ProductTypeForTestInactive(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=uuid4(),
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTest.new(
            int_field=3,
            str_field="",
            sub_block=SubBlockForTest.new(int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.INITIAL,
    )

    ProductTypeForTestInactive(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=uuid4(),
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTestInactive.new(int_field=3),
        status=SubscriptionLifecycle.INITIAL,
    )

    ProductTypeForTestProvisioning(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=uuid4(),
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTest.new(
            int_field=3,
            str_field="",
            sub_block=SubBlockForTest.new(int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.PROVISIONING,
    )

    ProductTypeForTest(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=uuid4(),
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTest.new(
            int_field=3,
            str_field="",
            sub_block=SubBlockForTest.new(int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.ACTIVE,
    )

    ProductTypeForTest(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=uuid4(),
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=BlockForTest.new(
            int_field=3,
            str_field="",
            sub_block=SubBlockForTest.new(int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.INITIAL,
    )

    with pytest.raises(
        ValidationError,
        match=r"2 validation errors for SubBlockForTest\nint_field\n  field required .+\nstr_field\n  field required .+",
    ):
        ProductTypeForTest(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=uuid4(),
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            block=BlockForTest.new(),
            status=SubscriptionLifecycle.ACTIVE,
        )

    with pytest.raises(ValidationError, match=r"6 validation errors for ProductTypeForTest"):
        ProductTypeForTest(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=uuid4(),
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            block=BlockForTestInactive.new(),
            status=SubscriptionLifecycle.ACTIVE,
        )

    with pytest.raises(ValidationError, match=r"1 validation error for ProductTypeForTest\nblock\n  field required .+"):
        ProductTypeForTest(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=uuid4(),
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            status=SubscriptionLifecycle.INITIAL,
        )

    with pytest.raises(ValidationError, match=r"1 validation error for ProductTypeForTest\nblock\n  field required .+"):
        ProductTypeForTest(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=uuid4(),
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            status=SubscriptionLifecycle.ACTIVE,
        )


def test_change_lifecycle(test_product_model, test_product_type, test_product_block):
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    product_type = ProductTypeForTestInactive(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=uuid4(),
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        status=SubscriptionLifecycle.INITIAL,
        block=BlockForTestInactive.new(),
    )

    # Does not work if constraints are not met
    with pytest.raises(ValidationError, match=r"int_field\n  none is not an allowed value"):
        product_type = change_lifecycle(product_type, SubscriptionLifecycle.ACTIVE)
    with pytest.raises(ValidationError, match=r"int_field\n  none is not an allowed value"):
        product_type = change_lifecycle(product_type, SubscriptionLifecycle.PROVISIONING)

    # Set first value
    product_type.block.int_field = 3
    product_type.block.sub_block.int_field = 3
    product_type.block.sub_block_2.int_field = 3

    # Does not work if constraints are not met
    with pytest.raises(ValidationError, match=r"str_field\n  none is not an allowed value"):
        product_type = change_lifecycle(product_type, SubscriptionLifecycle.ACTIVE)

    # works with correct data
    product_type = change_lifecycle(product_type, SubscriptionLifecycle.PROVISIONING)
    assert product_type.status == SubscriptionLifecycle.PROVISIONING
    assert product_type.block.str_field is None

    product_type.block.str_field = ""
    product_type.block.sub_block.str_field = ""
    product_type.block.sub_block_2.str_field = ""

    # works with correct data
    product_type = change_lifecycle(product_type, SubscriptionLifecycle.ACTIVE)
    assert product_type.status == SubscriptionLifecycle.ACTIVE


def test_update_constrained_lists(test_product, test_product_block):
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block

    class TestConListProductType(SubscriptionModel, is_base=True):
        saps: conlist(BlockForTestInactive, min_items=1, max_items=4)

    # Creates
    ip = TestConListProductType.from_product_id(product_id=test_product, customer_id=uuid4())
    ip.save()

    sap = BlockForTestInactive.new(int_field=3, str_field="")

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

    sap = BlockForTestInactive.new(int_field=3, str_field="")

    # Set new saps
    ip.saps = [sap]

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


def test_domain_model_attrs_saving_loading(test_product, test_product_type):
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    test_model = ProductTypeForTestInactive.from_product_id(product_id=test_product, customer_id=uuid4())
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

    test_model_2 = ProductTypeForTestInactive.from_subscription(test_model.subscription_id)
    assert test_model == test_model_2


def test_removal_of_domain_attrs(test_product, test_product_type):
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    test_model = ProductTypeForTestInactive.from_product_id(product_id=test_product, customer_id=uuid4())
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
