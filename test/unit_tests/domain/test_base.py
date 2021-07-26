from datetime import datetime
from typing import List, Optional, TypeVar
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
from orchestrator.domain.lifecycle import ProductLifecycle, change_lifecycle
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

    db.session.add(product_block)
    db.session.add(product_sub_block)
    db.session.commit()

    return [product_block, product_sub_block]


@pytest.fixture
def test_product(test_product_blocks_db):
    product = ProductTable(
        name="TestProduct", description="Test ProductTable", product_type="Test", tag="TEST", status="active"
    )

    fixed_input = FixedInputTable(name="test_fixed_input", value="False")

    product.fixed_inputs = [fixed_input]
    product.product_blocks = test_product_blocks_db

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


def test_product_block_metadata(test_product_block, test_product_blocks_db):
    block_db_model, _ = test_product_blocks_db
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block

    BlockForTestInactive.new()  # Need at least one instance since we lazy load this stuff

    assert BlockForTestInactive.name == "BlockForTest"
    assert BlockForTestInactive.description == "Test Block"
    assert BlockForTestInactive.product_block_id == block_db_model.product_block_id
    assert BlockForTestInactive.tag == "TEST"


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
            test_fixed_input=False,
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
        test_fixed_input=False,
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
            list_field=[1],
            sub_block=SubBlockForTest.new(int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.INITIAL,
        test_fixed_input=False,
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
            list_field=[1],
            sub_block=SubBlockForTest.new(int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
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
            subscription_id=uuid4(),
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            block=BlockForTestProvisioning.new(
                int_field=3,
                list_field=[1],
                sub_block=SubBlockForTestProvisioning.new(int_field=3),
                sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
            ),
            status=SubscriptionLifecycle.ACTIVE,
            test_fixed_input=False,
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
            list_field=[1],
            sub_block=SubBlockForTestProvisioning.new(int_field=3),
            sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
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
            list_field=[1],
            sub_block=SubBlockForTest.new(int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.INITIAL,
        test_fixed_input=False,
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
        test_fixed_input=False,
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
            list_field=[1],
            sub_block=SubBlockForTest.new(int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.PROVISIONING,
        test_fixed_input=False,
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
            list_field=[1],
            sub_block=SubBlockForTest.new(int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.ACTIVE,
        test_fixed_input=False,
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
            list_field=[1],
            sub_block=SubBlockForTest.new(int_field=3, str_field=""),
            sub_block_2=SubBlockForTest.new(int_field=3, str_field=""),
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
            subscription_id=uuid4(),
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            block=BlockForTest.new(),
            status=SubscriptionLifecycle.ACTIVE,
            test_fixed_input=False,
        )

    with pytest.raises(ValidationError, match=r"5 validation errors for ProductTypeForTest"):
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
            test_fixed_input=False,
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
            test_fixed_input=False,
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
            test_fixed_input=False,
        )


def test_change_lifecycle(test_product_model, test_product_type, test_product_block, test_product_sub_block):
    SubBlockForTestInactive, SubBlockForTestProvisioning, SubBlockForTest = test_product_sub_block
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
        block=BlockForTestInactive.new(sub_block_2=SubBlockForTestInactive.new()),
        test_fixed_input=False,
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
    product_type.block.sub_block_list = [SubBlockForTestInactive.new()]
    product_type.block.sub_block_list[0].int_field = 4
    product_type.block.list_field = [1]

    # Does not work if constraints are not met
    with pytest.raises(ValidationError, match=r"str_field\n  none is not an allowed value"):
        product_type = change_lifecycle(product_type, SubscriptionLifecycle.ACTIVE)

    # works with correct data
    product_type = change_lifecycle(product_type, SubscriptionLifecycle.PROVISIONING)
    assert product_type.status == SubscriptionLifecycle.PROVISIONING
    assert product_type.block.str_field is None

    product_type.block.str_field = "A"
    product_type.block.sub_block.str_field = "B"
    product_type.block.sub_block_2.str_field = "C"
    product_type.block.sub_block_list[0].str_field = "D"

    # works with correct data
    product_type_new = change_lifecycle(product_type, SubscriptionLifecycle.ACTIVE)
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
            },
            "sub_block_2": None,
            "sub_block_list": [],
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
    model.block.sub_block_2 = SubBlockForTestInactive.new()
    model.block.sub_block_2.int_field = 3
    model.block.list_field = [1]
    model.block.sub_block.str_field = "B"
    model.block.sub_block_2.str_field = "C"

    # works with correct data
    model = change_lifecycle(model, SubscriptionLifecycle.ACTIVE)

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


def test_update_optional(test_product, test_product_block):
    BlockForTestInactive, BlockForTestProvisioning, BlockForTest = test_product_block

    class TestListProductType(SubscriptionModel, is_base=True):
        sap: Optional[BlockForTestInactive] = None

    # Creates
    ip = TestListProductType.from_product_id(product_id=test_product, customer_id=uuid4())
    ip.save()

    sap = BlockForTestInactive.new(int_field=3, str_field="")

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
    test_model.block.sub_block_2 = SubBlockForTestInactive.new()
    test_model.block.sub_block_list = [SubBlockForTestInactive.new()]
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
    test_model.block.sub_block_2 = SubBlockForTestInactive.new()

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
    block_db_model, _ = test_product_blocks_db
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
    test_model.block = BlockForTestInactive.new()

    # Check metadata
    with pytest.raises(ValueError, match=r"Cannot create instance of abstract class. Use one of {'BlockForTest'}"):
        AbstractBlockForTestInactive.new()
    assert AbstractBlockForTestInactive.name is None
    assert not hasattr(AbstractBlockForTestInactive, "description")
    assert not hasattr(AbstractBlockForTestInactive, "product_block_id")
    assert not hasattr(AbstractBlockForTestInactive, "tag")
    assert BlockForTestInactive.name == "BlockForTest"
    assert BlockForTestInactive.description == "Test Block"
    assert BlockForTestInactive.product_block_id == block_db_model.product_block_id
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

    test_model = change_lifecycle(test_model, SubscriptionLifecycle.ACTIVE)
    test_model.save()

    test_model = AbstractProductTypeForTest.from_subscription(test_model.subscription_id)
    assert isinstance(test_model.block, AbstractBlockForTest)

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

    assert Wrong.diff_product_in_database(test_product) == {
        "missing_fixed_inputs_in_db": {
            "customer_id",
            "description",
            "end_date",
            "insync",
            "note",
            "product",
            "start_date",
            "status",
            "subscription_id",
        },
        "missing_fixed_inputs_in_model": {"test_fixed_input"},
        "missing_product_blocks_in_model": {"BlockForTest", "SubBlockForTest"},
    }


def test_diff_in_db_missing_in_db(test_product_type):
    ProductTypeForTestInactive, ProductTypeForTestProvisioning, ProductTypeForTest = test_product_type

    product = ProductTable(
        name="TestProductEmpty", description="Test ProductTable", product_type="Test", tag="TEST", status="active"
    )

    db.session.add(product)
    db.session.commit()

    assert ProductTypeForTestInactive.diff_product_in_database(product.product_id) == {
        "missing_fixed_inputs_in_db": {"test_fixed_input"},
        "missing_product_blocks_in_db": ["SubBlockForTest", "SubBlockForTest", "SubBlockForTest", "BlockForTest"],
        "missing_resource_types_in_db": {
            "BlockForTest": {"int_field", "list_field", "str_field"},
            "SubBlockForTest": {"int_field", "str_field"},
        },
    }
