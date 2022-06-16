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
    ProductTable,
    SubscriptionInstanceRelationTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    db,
)
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import (
    ProductBlockModel,
    SubscriptionInstanceList,
    SubscriptionModel,
    _is_constrained_list_type,
)
from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.types import SubscriptionLifecycle
from test.unit_tests.fixtures.products.product_blocks.product_block_list_nested import (
    ProductBlockListNestedForTestInactive,
)
from test.unit_tests.fixtures.products.product_blocks.product_block_one_nested import (
    ProductBlockOneNestedForTestInactive,
)


def test_product_block_metadata(test_product_block_one, test_product_one, test_product_block_one_db):
    ProductBlockOneForTestInactive, _, _ = test_product_block_one

    subscription_id = uuid4()
    ProductBlockOneForTestInactive.new(
        subscription_id=subscription_id
    )  # Need at least one instance since we lazy load this stuff

    product_block, _ = test_product_block_one_db

    assert ProductBlockOneForTestInactive.name == "ProductBlockOneForTest"
    assert ProductBlockOneForTestInactive.description == "Test Block"
    assert ProductBlockOneForTestInactive.product_block_id == product_block.product_block_id
    assert ProductBlockOneForTestInactive.tag == "TEST"


def test_product_block_one_nested(test_product_model_nested, test_product_type_one_nested):
    """Test the behavior of nesting (self-referencing) product blocks.

    Notes:
        - nesting only works when each block is attached to a different subscription

    """
    ProductTypeOneNestedForTestInactive, _, ProductTypeOneNestedForTest = test_product_type_one_nested

    customer_id = uuid4()
    # Create productblock 30 that will be nested in block 20
    model30 = ProductTypeOneNestedForTestInactive.from_product_id(
        product_id=test_product_model_nested.product_id,
        customer_id=customer_id,
        insync=True,
        start_date=None,
        status=SubscriptionLifecycle.INITIAL,
    )
    model30.block = ProductBlockOneNestedForTestInactive.new(
        subscription_id=model30.subscription_id,
        int_field=30,
        sub_block=None,
    )
    model30 = SubscriptionModel.from_other_lifecycle(model30, SubscriptionLifecycle.ACTIVE)
    model30.save()
    db.session.commit()

    # Create productblock 20 that refers to block 30, and will be nested in block 10
    model20 = ProductTypeOneNestedForTestInactive.from_product_id(
        product_id=test_product_model_nested.product_id,
        customer_id=customer_id,
        insync=True,
        start_date=None,
        status=SubscriptionLifecycle.INITIAL,
    )
    model20.block = ProductBlockOneNestedForTestInactive.new(
        subscription_id=model20.subscription_id,
        int_field=20,
        sub_block=model30.block,
    )
    model20 = SubscriptionModel.from_other_lifecycle(model20, SubscriptionLifecycle.ACTIVE)
    model20.save()
    db.session.commit()

    # Create productblock 10 that refers to block 20
    model10 = ProductTypeOneNestedForTestInactive.from_product_id(
        product_id=test_product_model_nested.product_id,
        customer_id=customer_id,
        insync=True,
        start_date=None,
        status=SubscriptionLifecycle.INITIAL,
    )
    model10.block = ProductBlockOneNestedForTestInactive.new(
        subscription_id=model10.subscription_id, int_field=10, sub_block=model20.block
    )
    model10 = SubscriptionModel.from_other_lifecycle(model10, SubscriptionLifecycle.ACTIVE)
    model10.save()
    db.session.commit()

    # Load block 10 and verify the nested blocks
    newmodel10 = ProductTypeOneNestedForTest.from_subscription(model10.subscription_id)
    assert newmodel10.block.int_field == 10
    assert newmodel10.block.sub_block.int_field == 20
    assert newmodel10.block.sub_block.sub_block.int_field == 30
    assert newmodel10.block.sub_block.sub_block.sub_block is None

    # Load block 20 and verify the nested block
    newmodel20 = ProductTypeOneNestedForTest.from_subscription(model20.subscription_id)
    assert newmodel20.block.int_field == 20
    assert newmodel20.block.sub_block.int_field == 30
    assert newmodel20.block.sub_block.sub_block is None

    # Create productblock 11 that also refers to block 20
    model11 = ProductTypeOneNestedForTestInactive.from_product_id(
        product_id=test_product_model_nested.product_id,
        customer_id=customer_id,
        insync=True,
        start_date=None,
        status=SubscriptionLifecycle.INITIAL,
    )
    model11.block = ProductBlockOneNestedForTestInactive.new(
        subscription_id=model11.subscription_id, int_field=11, sub_block=model20.block
    )
    model11 = SubscriptionModel.from_other_lifecycle(model11, SubscriptionLifecycle.ACTIVE)
    model11.save()
    db.session.commit()

    # Load block 11 and verify the nested blocks
    newmodel11 = ProductTypeOneNestedForTest.from_subscription(model11.subscription_id)
    assert newmodel11.block.int_field == 11
    assert newmodel11.block.sub_block.int_field == 20
    assert newmodel11.block.sub_block.sub_block.int_field == 30
    assert newmodel11.block.sub_block.sub_block.sub_block is None

    # (again) Load block 10 and verify the nested blocks are same as before
    newmodel10 = ProductTypeOneNestedForTest.from_subscription(model10.subscription_id)
    assert newmodel10.block.int_field == 10
    assert newmodel10.block.sub_block.int_field == 20
    assert newmodel10.block.sub_block.sub_block.int_field == 30
    assert newmodel10.block.sub_block.sub_block.sub_block is None

    # Below part might not be interesting to test, or better off in a separate testcase.
    # I was just curious what happens when we delete things.

    # Remove block 20 from block 10
    model10.block.sub_block = None
    model10.save()
    db.session.commit()

    # Load block 10 and verify the nested block is removed
    newmodel10 = ProductTypeOneNestedForTest.from_subscription(model10.subscription_id)
    assert newmodel10.block.int_field == 10
    assert newmodel10.block.sub_block is None

    # Load block 11 and verify the nested blocks still exist
    newmodel11 = ProductTypeOneNestedForTest.from_subscription(model11.subscription_id)
    assert newmodel11.block.int_field == 11
    assert newmodel11.block.sub_block.int_field == 20
    assert newmodel11.block.sub_block.sub_block.int_field == 30
    assert newmodel11.block.sub_block.sub_block.sub_block is None


def test_product_block_list_nested(test_product_model_list_nested, test_product_type_list_nested):
    """Test the behavior of nesting (self-referencing) a list of product blocks.

    Notes:
        - nesting only works when each block is attached to a different subscription

    """
    ProductTypeListNestedForTestInactive, _, ProductTypeListNestedForTest = test_product_type_list_nested

    customer_id = uuid4()
    # Create productblocks 30 and 31 that will both be nested in block 20 and 21
    model30 = ProductTypeListNestedForTestInactive.from_product_id(
        product_id=test_product_model_list_nested.product_id,
        customer_id=customer_id,
        insync=True,
        start_date=None,
        status=SubscriptionLifecycle.INITIAL,
    )
    model30.block = ProductBlockListNestedForTestInactive.new(
        subscription_id=model30.subscription_id,
        int_field=30,
        sub_block_list=[],
    )
    model30 = SubscriptionModel.from_other_lifecycle(model30, SubscriptionLifecycle.ACTIVE)
    model30.save()
    model31 = ProductTypeListNestedForTestInactive.from_product_id(
        product_id=test_product_model_list_nested.product_id,
        customer_id=customer_id,
        insync=True,
        start_date=None,
        status=SubscriptionLifecycle.INITIAL,
    )
    model31.block = ProductBlockListNestedForTestInactive.new(
        subscription_id=model31.subscription_id,
        int_field=31,
        sub_block_list=[],
    )
    model31 = SubscriptionModel.from_other_lifecycle(model31, SubscriptionLifecycle.ACTIVE)
    model31.save()
    db.session.commit()

    # Create productblocks 20 and 21 that both
    # - refer to blocks 30 and 31
    # - will be nested in blocks 10 and 11
    model20 = ProductTypeListNestedForTestInactive.from_product_id(
        product_id=test_product_model_list_nested.product_id,
        customer_id=customer_id,
        insync=True,
        start_date=None,
        status=SubscriptionLifecycle.INITIAL,
    )
    model20.block = ProductBlockListNestedForTestInactive.new(
        subscription_id=model20.subscription_id,
        int_field=20,
        sub_block_list=[model30.block, model31.block],
    )
    model20 = SubscriptionModel.from_other_lifecycle(model20, SubscriptionLifecycle.ACTIVE)
    model20.save()
    model21 = ProductTypeListNestedForTestInactive.from_product_id(
        product_id=test_product_model_list_nested.product_id,
        customer_id=customer_id,
        insync=True,
        start_date=None,
        status=SubscriptionLifecycle.INITIAL,
    )
    model21.block = ProductBlockListNestedForTestInactive.new(
        subscription_id=model21.subscription_id,
        int_field=21,
        sub_block_list=[model30.block, model31.block],
    )
    model21 = SubscriptionModel.from_other_lifecycle(model21, SubscriptionLifecycle.ACTIVE)
    model21.save()
    db.session.commit()

    # Create productblocks 10 and 11 that both refer to blocks 20 and 21
    model10 = ProductTypeListNestedForTestInactive.from_product_id(
        product_id=test_product_model_list_nested.product_id,
        customer_id=customer_id,
        insync=True,
        start_date=None,
        status=SubscriptionLifecycle.INITIAL,
    )
    model10.block = ProductBlockListNestedForTestInactive.new(
        subscription_id=model10.subscription_id,
        int_field=10,
        sub_block_list=[model20.block, model21.block],
    )
    model10 = SubscriptionModel.from_other_lifecycle(model10, SubscriptionLifecycle.ACTIVE)
    model10.save()
    model11 = ProductTypeListNestedForTestInactive.from_product_id(
        product_id=test_product_model_list_nested.product_id,
        customer_id=customer_id,
        insync=True,
        start_date=None,
        status=SubscriptionLifecycle.INITIAL,
    )
    model11.block = ProductBlockListNestedForTestInactive.new(
        subscription_id=model11.subscription_id,
        int_field=11,
        sub_block_list=[model20.block, model21.block],
    )
    model11 = SubscriptionModel.from_other_lifecycle(model11, SubscriptionLifecycle.ACTIVE)
    model11.save()
    db.session.commit()

    # Load blocks 10 and 11 and verify the nested blocks
    newmodel10 = ProductTypeListNestedForTest.from_subscription(model10.subscription_id)
    newmodel11 = ProductTypeListNestedForTest.from_subscription(model11.subscription_id)
    assert newmodel10.block.int_field == 10
    assert newmodel11.block.int_field == 11
    assert newmodel10.block.sub_block_list[0].int_field == 20
    assert newmodel10.block.sub_block_list[1].int_field == 21
    assert newmodel11.block.sub_block_list[0].int_field == 20
    assert newmodel11.block.sub_block_list[1].int_field == 21
    assert sorted(
        level3.int_field for level2 in newmodel10.block.sub_block_list for level3 in level2.sub_block_list
    ) == [30, 30, 31, 31]
    assert sorted(
        level3.int_field for level2 in newmodel11.block.sub_block_list for level3 in level2.sub_block_list
    ) == [30, 30, 31, 31]
    # Assert a few blocks at deepest level to have an empty list
    assert newmodel10.block.sub_block_list[0].sub_block_list[0].sub_block_list == []
    assert newmodel11.block.sub_block_list[1].sub_block_list[1].sub_block_list == []

    # Load block 20 and verify nested blocks
    newmodel20 = ProductTypeListNestedForTest.from_subscription(model20.subscription_id)
    assert newmodel20.block.int_field == 20
    assert newmodel20.block.sub_block_list[0].int_field == 30
    assert newmodel20.block.sub_block_list[1].int_field == 31
    assert newmodel20.block.sub_block_list[0].sub_block_list == []

    # Create productblock 32 and nest it in block 20 (but not 21!)
    model32 = ProductTypeListNestedForTestInactive.from_product_id(
        product_id=test_product_model_list_nested.product_id,
        customer_id=customer_id,
        insync=True,
        start_date=None,
        status=SubscriptionLifecycle.INITIAL,
    )
    model32.block = ProductBlockListNestedForTestInactive.new(
        subscription_id=model30.subscription_id,
        int_field=32,
        sub_block_list=[],
    )
    model32 = SubscriptionModel.from_other_lifecycle(model32, SubscriptionLifecycle.ACTIVE)
    model32.save()
    newmodel20.block.sub_block_list.append(model32.block)
    newmodel20.save()
    db.session.commit()

    # (again) Load blocks 10 and 11 and verify block 32 is present once
    newmodel10 = ProductTypeListNestedForTest.from_subscription(model10.subscription_id)
    newmodel11 = ProductTypeListNestedForTest.from_subscription(model11.subscription_id)
    assert sorted(
        level3.int_field for level2 in newmodel10.block.sub_block_list for level3 in level2.sub_block_list
    ) == [30, 30, 31, 31, 32]
    assert sorted(
        level3.int_field for level2 in newmodel11.block.sub_block_list for level3 in level2.sub_block_list
    ) == [30, 30, 31, 31, 32]


def test_lifecycle(test_product_model, test_product_type_one, test_product_block_one):
    ProductBlockOneForTestInactive, _, _ = test_product_block_one
    ProductTypeOneForTestInactive, _, _ = test_product_type_one
    subscription_id = uuid4()

    # Test create with wrong lifecycle, we can create
    with pytest.raises(ValueError, match=r"is not valid for status active"):
        ProductTypeOneForTestInactive(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=subscription_id,
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            block=ProductBlockOneForTestInactive.new(subscription_id),
            status=SubscriptionLifecycle.ACTIVE,
            test_fixed_input=False,
        )

    # Works with right lifecycle
    product_type = ProductTypeOneForTestInactive(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=ProductBlockOneForTestInactive.new(subscription_id),
        status=SubscriptionLifecycle.INITIAL,
        test_fixed_input=False,
    )

    assert product_type.status == SubscriptionLifecycle.INITIAL


def test_lifecycle_specific(
    test_product_model, test_product_type_one, test_product_block_one, test_product_sub_block_one
):
    _, SubBlockOneForTestProvisioning, SubBlockOneForTest = test_product_sub_block_one
    _, ProductBlockOneForTestProvisioning, ProductBlockOneForTest = test_product_block_one
    _, ProductTypeOneForTestProvisioning, ProductTypeOneForTest = test_product_type_one
    subscription_id = uuid4()

    # Works with less contrained lifecycle
    product_type = ProductTypeOneForTest(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=ProductBlockOneForTest.new(
            subscription_id=subscription_id,
            int_field=3,
            str_field="",
            list_field=[1],
            sub_block=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.INITIAL,
        test_fixed_input=False,
    )

    assert product_type.status == SubscriptionLifecycle.INITIAL

    # Works with right lifecycle
    product_type = ProductTypeOneForTest(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=ProductBlockOneForTest.new(
            subscription_id=subscription_id,
            int_field=3,
            str_field="",
            list_field=[1],
            sub_block=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.ACTIVE,
        test_fixed_input=False,
    )

    assert product_type.status == SubscriptionLifecycle.ACTIVE

    # Does not work with more constrained lifecycle
    with pytest.raises(ValueError, match=r"is not valid for status active"):
        ProductTypeOneForTestProvisioning(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=subscription_id,
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            block=ProductBlockOneForTestProvisioning.new(
                subscription_id=subscription_id,
                int_field=3,
                list_field=[1],
                sub_block=SubBlockOneForTestProvisioning.new(subscription_id=subscription_id, int_field=3),
                sub_block_2=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            ),
            status=SubscriptionLifecycle.ACTIVE,
            test_fixed_input=False,
        )

    # Works with right lifecycle
    product_type = ProductTypeOneForTestProvisioning(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=ProductBlockOneForTestProvisioning.new(
            subscription_id=subscription_id,
            int_field=3,
            list_field=[1],
            sub_block=SubBlockOneForTestProvisioning.new(subscription_id=subscription_id, int_field=3),
            sub_block_2=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.PROVISIONING,
        test_fixed_input=False,
    )
    assert product_type.status == SubscriptionLifecycle.PROVISIONING


def test_product_blocks_per_lifecycle(
    test_product_model, test_product_type_one, test_product_block_one, test_product_sub_block_one
):
    _, _, SubBlockOneForTest = test_product_sub_block_one
    ProductBlockOneForTestInactive, _, ProductBlockOneForTest = test_product_block_one
    ProductTypeOneForTestInactive, ProductTypeOneForTestProvisioning, ProductTypeOneForTest = test_product_type_one
    subscription_id = uuid4()

    ProductTypeOneForTestInactive(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=ProductBlockOneForTest.new(
            subscription_id=subscription_id,
            int_field=3,
            str_field="",
            list_field=[1],
            sub_block=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.INITIAL,
        test_fixed_input=False,
    )

    ProductTypeOneForTestInactive(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=ProductBlockOneForTestInactive.new(subscription_id=subscription_id, int_field=3),
        status=SubscriptionLifecycle.INITIAL,
        test_fixed_input=False,
    )

    ProductTypeOneForTestProvisioning(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=ProductBlockOneForTest.new(
            subscription_id=subscription_id,
            int_field=3,
            str_field="",
            list_field=[1],
            sub_block=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.PROVISIONING,
        test_fixed_input=False,
    )

    ProductTypeOneForTest(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=ProductBlockOneForTest.new(
            subscription_id=subscription_id,
            int_field=3,
            str_field="",
            list_field=[1],
            sub_block=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.ACTIVE,
        test_fixed_input=False,
    )

    ProductTypeOneForTest(
        product=test_product_model,
        customer_id=uuid4(),
        subscription_id=subscription_id,
        insync=False,
        description="",
        start_date=None,
        end_date=None,
        note=None,
        block=ProductBlockOneForTest.new(
            subscription_id=subscription_id,
            int_field=3,
            str_field="",
            list_field=[1],
            sub_block=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.INITIAL,
        test_fixed_input=False,
    )

    with pytest.raises(
        ValidationError,
        match=r"2 validation errors for SubBlockOneForTest\nint_field\n  field required .+\nstr_field\n  field required .+",
    ):
        ProductTypeOneForTest(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=subscription_id,
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            block=ProductBlockOneForTest.new(subscription_id=subscription_id),
            status=SubscriptionLifecycle.ACTIVE,
            test_fixed_input=False,
        )

    with pytest.raises(ValidationError, match=r"5 validation errors for ProductTypeOneForTest"):
        ProductTypeOneForTest(
            product=test_product_model,
            customer_id=uuid4(),
            subscription_id=subscription_id,
            insync=False,
            description="",
            start_date=None,
            end_date=None,
            note=None,
            block=ProductBlockOneForTestInactive.new(subscription_id=subscription_id),
            status=SubscriptionLifecycle.ACTIVE,
            test_fixed_input=False,
        )

    with pytest.raises(
        ValidationError, match=r"1 validation error for ProductTypeOneForTest\nblock\n  field required .+"
    ):
        ProductTypeOneForTest(
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

    with pytest.raises(
        ValidationError, match=r"1 validation error for ProductTypeOneForTest\nblock\n  field required .+"
    ):
        ProductTypeOneForTest(
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


def test_change_lifecycle(test_product_one, test_product_type_one, test_product_block_one, test_product_sub_block_one):
    SubBlockOneForTestInactive, _, _ = test_product_sub_block_one
    ProductBlockOneForTestInactive, _, _ = test_product_block_one
    ProductTypeOneForTestInactive, _, _ = test_product_type_one

    product_type = ProductTypeOneForTestInactive.from_product_id(
        test_product_one,
        uuid4(),
    )
    product_type.block = ProductBlockOneForTestInactive.new(
        subscription_id=product_type.subscription_id,
        sub_block_2=SubBlockOneForTestInactive.new(subscription_id=product_type.subscription_id),
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
    product_type.block.sub_block_list = [SubBlockOneForTestInactive.new(subscription_id=product_type.subscription_id)]
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


def test_save_load(test_product_model, test_product_type_one, test_product_block_one, test_product_sub_block_one):
    SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest = test_product_sub_block_one
    ProductBlockOneForTestInactive, ProductBlockOneForTestProvisioning, ProductBlockOneForTest = test_product_block_one
    ProductTypeOneForTestInactive, ProductTypeOneForTestProvisioning, ProductTypeOneForTest = test_product_type_one

    customer_id = uuid4()

    model = ProductTypeOneForTestInactive.from_product_id(
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
            "name": "ProductBlockOneForTest",
            "str_field": "A",
            "sub_block": {
                "int_field": None,
                "label": None,
                "name": "SubBlockOneForTest",
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
            "name": "TestProductOne",
            "product_id": test_product_model.product_id,
            "product_type": "Test",
            "status": ProductLifecycle.ACTIVE,
            "tag": "TEST",
            "created_at": test_product_model.created_at,
            "end_date": None,
        },
        "start_date": datetime(2021, 1, 1, 1, 1, 1, tzinfo=pytz.utc),
        "status": SubscriptionLifecycle.INITIAL,
        "subscription_id": mock.ANY,
        "test_fixed_input": False,
    }

    # Set first value
    model.block.int_field = 3
    model.block.sub_block.int_field = 3
    model.block.sub_block_2 = SubBlockOneForTestInactive.new(subscription_id=model.subscription_id)
    model.block.sub_block_2.int_field = 3
    model.block.list_field = [1]
    model.block.sub_block.str_field = "B"
    model.block.sub_block_2.str_field = "C"

    # works with correct data
    model = SubscriptionModel.from_other_lifecycle(model, SubscriptionLifecycle.ACTIVE)

    model.save()
    db.session.commit()

    new_model = ProductTypeOneForTest.from_subscription(model.subscription_id)
    assert model.dict() == new_model.dict()

    # Second save also works as expected
    new_model.save()
    db.session.commit()

    latest_model = ProductTypeOneForTest.from_subscription(model.subscription_id)
    assert new_model.dict() == latest_model.dict()

    # Loading blocks also works
    block = ProductBlockOneForTest.from_db(model.block.subscription_instance_id)
    assert block.dict() == model.block.dict()


def test_update_constrained_lists(test_product_one, test_product_block_one):
    ProductBlockOneForTestInactive, _, _ = test_product_block_one

    class TestConListProductType(SubscriptionModel, is_base=True):
        saps: conlist(ProductBlockOneForTestInactive, min_items=1, max_items=4)

    # Creates
    ip = TestConListProductType.from_product_id(product_id=test_product_one, customer_id=uuid4())
    ip.save()

    sap = ProductBlockOneForTestInactive.new(subscription_id=ip.subscription_id, int_field=3, str_field="")

    # Set new saps, removes old one
    ip.saps = [sap]

    ip.save()

    ip2 = TestConListProductType.from_subscription(ip.subscription_id)

    # Old default saps should not be saved
    assert ip.dict() == ip2.dict()

    # Test constraint
    with pytest.raises(ValidationError):
        ip.saps = []


def test_update_lists(test_product_one, test_product_block_one):
    ProductBlockOneForTestInactive, _, _ = test_product_block_one

    class TestListProductType(SubscriptionModel, is_base=True):
        saps: List[ProductBlockOneForTestInactive]

    # Creates
    ip = TestListProductType.from_product_id(product_id=test_product_one, customer_id=uuid4())
    ip.save()

    sap = ProductBlockOneForTestInactive.new(subscription_id=ip.subscription_id, int_field=3, str_field="")

    # Set new saps
    ip.saps = [sap]

    ip.save()

    ip2 = TestListProductType.from_subscription(ip.subscription_id)

    # Old default saps should not be saved
    assert ip.dict() == ip2.dict()


def test_update_optional(test_product_one, test_product_block_one):
    ProductBlockOneForTestInactive, _, _ = test_product_block_one

    class TestListProductType(SubscriptionModel, is_base=True):
        sap: Optional[ProductBlockOneForTestInactive] = None

    # Creates
    ip = TestListProductType.from_product_id(product_id=test_product_one, customer_id=uuid4())
    ip.save()

    sap = ProductBlockOneForTestInactive.new(subscription_id=ip.subscription_id, int_field=3, str_field="")

    # Set new sap
    ip.sap = sap

    ip.save()

    ip2 = TestListProductType.from_subscription(ip.subscription_id)

    # Old default saps should not be saved
    assert ip.dict() == ip2.dict()


def test_generic_from_subscription(test_product_one, test_product_type_one):
    ProductTypeOneForTestInactive, _, _ = test_product_type_one

    ip = ProductTypeOneForTestInactive.from_product_id(product_id=test_product_one, customer_id=uuid4())
    ip.save()

    model = SubscriptionModel.from_subscription(ip.subscription_id)

    assert isinstance(model, ProductTypeOneForTestInactive)


def test_label_is_saved(test_product_one, test_product_type_one):
    ProductTypeOneForTestInactive, _, _ = test_product_type_one

    test_model = ProductTypeOneForTestInactive.from_product_id(test_product_one, uuid4())
    test_model.block.label = "My label"
    test_model.save()
    db.session.commit()
    instance_in_db = SubscriptionInstanceTable.query.get(test_model.block.subscription_instance_id)
    assert instance_in_db.label == "My label"


def test_domain_model_attrs_saving_loading(test_product_one, test_product_type_one, test_product_sub_block_one):
    SubBlockOneForTestInactive, _, _ = test_product_sub_block_one
    ProductTypeOneForTestInactive, _, _ = test_product_type_one

    test_model = ProductTypeOneForTestInactive.from_product_id(product_id=test_product_one, customer_id=uuid4())
    test_model.block.sub_block_2 = SubBlockOneForTestInactive.new(subscription_id=test_model.subscription_id)
    test_model.block.sub_block_list = [SubBlockOneForTestInactive.new(subscription_id=test_model.subscription_id)]
    test_model.save()
    db.session.commit()

    relation = SubscriptionInstanceRelationTable.query.filter(
        SubscriptionInstanceRelationTable.depends_on_id == test_model.block.sub_block.subscription_instance_id
    ).one()
    assert relation.domain_model_attr == "sub_block"
    relation = SubscriptionInstanceRelationTable.query.filter(
        SubscriptionInstanceRelationTable.depends_on_id == test_model.block.sub_block_2.subscription_instance_id
    ).one()
    assert relation.domain_model_attr == "sub_block_2"
    relation = SubscriptionInstanceRelationTable.query.filter(
        SubscriptionInstanceRelationTable.depends_on_id == test_model.block.sub_block_list[0].subscription_instance_id
    ).one()
    assert relation.domain_model_attr == "sub_block_list"
    test_model_2 = ProductTypeOneForTestInactive.from_subscription(test_model.subscription_id)
    assert test_model == test_model_2


def test_removal_of_domain_attrs(test_product_one, test_product_type_one, test_product_sub_block_one):
    SubBlockOneForTestInactive, _, _ = test_product_sub_block_one
    ProductTypeOneForTestInactive, _, _ = test_product_type_one

    test_model = ProductTypeOneForTestInactive.from_product_id(product_id=test_product_one, customer_id=uuid4())
    test_model.block.sub_block_2 = SubBlockOneForTestInactive.new(subscription_id=test_model.subscription_id)

    test_model.save()
    db.session.commit()
    relation = SubscriptionInstanceRelationTable.query.filter(
        SubscriptionInstanceRelationTable.depends_on_id == test_model.block.sub_block.subscription_instance_id
    ).one()
    relation.domain_model_attr = None
    db.session.commit()
    with pytest.raises(ValueError, match=r"Expected exactly one item in iterable, but got"):
        ProductTypeOneForTestInactive.from_subscription(test_model.subscription_id)


def test_simple_model_with_no_attrs(generic_subscription_1, generic_product_type_1):
    GenericProductOneInactive, GenericProductOne = generic_product_type_1
    model = GenericProductOne.from_subscription(subscription_id=generic_subscription_1)
    with pytest.raises(NoResultFound):
        SubscriptionInstanceRelationTable.query.filter(
            SubscriptionInstanceRelationTable.depends_on_id == model.pb_1.subscription_instance_id
        ).one()


def test_abstract_super_block(test_product_one, test_product_type_one, test_product_block_one_db):
    ProductTypeOneForTestInactive, ProductTypeOneForTestProvisioning, ProductTypeOneForTest = test_product_type_one

    class AbstractProductBlockOneForTestInactive(ProductBlockModel):
        str_field: Optional[str] = None
        list_field: List[int] = Field(default_factory=list)

    class AbstractProductBlockOneForTestProvisioning(
        AbstractProductBlockOneForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        str_field: Optional[str] = None
        list_field: List[int]

    class AbstractProductBlockOneForTest(
        AbstractProductBlockOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        str_field: str
        list_field: List[int]

    class ProductBlockOneForTestInactive(
        AbstractProductBlockOneForTestInactive, product_block_name="ProductBlockOneForTest"
    ):
        str_field: Optional[str] = None
        list_field: List[int] = Field(default_factory=list)
        int_field: Optional[int] = None

    class ProductBlockOneForTestProvisioning(
        ProductBlockOneForTestInactive,
        AbstractProductBlockOneForTestProvisioning,
        lifecycle=[SubscriptionLifecycle.PROVISIONING],
    ):
        str_field: Optional[str] = None
        list_field: List[int]
        int_field: int

    class ProductBlockOneForTest(
        ProductBlockOneForTestProvisioning, AbstractProductBlockOneForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        str_field: str
        list_field: List[int]
        int_field: int

    class AbstractProductTypeOneForTestInactive(SubscriptionModel):
        block: AbstractProductBlockOneForTestInactive

    class AbstractProductTypeOneForTestProvisioning(AbstractProductTypeOneForTestInactive):
        block: AbstractProductBlockOneForTestProvisioning

    class AbstractProductTypeOneForTest(AbstractProductTypeOneForTestProvisioning):
        block: AbstractProductBlockOneForTest

    class ProductTypeOneForTestInactive(AbstractProductTypeOneForTestInactive, is_base=True):
        block: ProductBlockOneForTestInactive

    class ProductTypeOneForTestProvisioning(
        ProductTypeOneForTestInactive,
        AbstractProductTypeOneForTestProvisioning,
        lifecycle=[SubscriptionLifecycle.PROVISIONING],
    ):
        block: ProductBlockOneForTestProvisioning

    class ProductTypeOneForTest(
        ProductTypeOneForTestProvisioning, AbstractProductTypeOneForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        block: ProductBlockOneForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTest

    test_model = ProductTypeOneForTestInactive.from_product_id(product_id=test_product_one, customer_id=uuid4())
    test_model.block = ProductBlockOneForTestInactive.new(subscription_id=test_model.subscription_id)

    product_block, product_sub_block = test_product_block_one_db

    # Check metadata
    with pytest.raises(
        ValueError, match=r"Cannot create instance of abstract class. Use one of {'ProductBlockOneForTest'}"
    ):
        AbstractProductBlockOneForTestInactive.new(subscription_id=test_model.subscription_id)
    assert AbstractProductBlockOneForTestInactive.name is None
    assert not hasattr(AbstractProductBlockOneForTestInactive, "description")
    assert not hasattr(AbstractProductBlockOneForTestInactive, "product_block_id")
    assert not hasattr(AbstractProductBlockOneForTestInactive, "tag")
    assert ProductBlockOneForTestInactive.name == "ProductBlockOneForTest"
    assert ProductBlockOneForTestInactive.description == "Test Block"
    assert ProductBlockOneForTestInactive.product_block_id == product_block.product_block_id
    assert ProductBlockOneForTestInactive.tag == "TEST"

    test_model.save()
    db.session.commit()

    test_model = AbstractProductTypeOneForTestInactive.from_subscription(test_model.subscription_id)
    assert isinstance(test_model, ProductTypeOneForTestInactive)
    assert isinstance(test_model.block, ProductBlockOneForTestInactive)

    test_model = ProductTypeOneForTestInactive.from_subscription(test_model.subscription_id)
    assert isinstance(test_model.block, ProductBlockOneForTestInactive)

    test_model.block.int_field = 1
    test_model.block.str_field = "bla"
    test_model.block.list_field = [1]

    test_model = SubscriptionModel.from_other_lifecycle(test_model, SubscriptionLifecycle.ACTIVE)
    test_model.save()
    assert isinstance(test_model.block, ProductBlockOneForTest)

    test_model = AbstractProductTypeOneForTest.from_subscription(test_model.subscription_id)
    assert isinstance(test_model.block, ProductBlockOneForTest)

    test_model = ProductTypeOneForTest.from_subscription(test_model.subscription_id)
    assert isinstance(test_model.block, ProductBlockOneForTest)

    block = AbstractProductBlockOneForTest.from_db(test_model.block.subscription_instance_id)
    assert block.dict() == test_model.block.dict()
    assert isinstance(block, ProductBlockOneForTest)

    block = ProductBlockOneForTest.from_db(test_model.block.subscription_instance_id)
    assert block.dict() == test_model.block.dict()
    assert isinstance(block, ProductBlockOneForTest)


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


def test_diff_in_db(test_product_one, test_product_type_one):
    ProductTypeOneForTestInactive, _, _ = test_product_type_one

    assert ProductTypeOneForTestInactive.diff_product_in_database(test_product_one) == {}

    class Wrong(SubscriptionModel):
        pass

    assert (
        Wrong.diff_product_in_database(test_product_one)
        == {
            "TestProductOne": {
                "missing_fixed_inputs_in_model": {"test_fixed_input"},
                "missing_product_blocks_in_model": {"ProductBlockOneForTest"},
            }
        }
        != {
            "TestProductOne": {
                "missing_in_depends_on_blocks": {
                    "ProductBlockOneForTest": {"missing_product_blocks_in_db": {"SubBlockOneForTest"}}
                },
                "missing_product_blocks_in_model": {"SubBlockOneForTest"},
            }
        }
    )


def test_diff_in_db_missing_in_db(test_product_type_one):
    ProductTypeOneForTestInactive, _, _ = test_product_type_one

    product = ProductTable(
        name="TestProductEmpty", description="Test ProductTable", product_type="Test", tag="TEST", status="active"
    )

    db.session.add(product)
    db.session.commit()

    assert ProductTypeOneForTestInactive.diff_product_in_database(product.product_id) == {
        "TestProductEmpty": {
            "missing_fixed_inputs_in_db": {"test_fixed_input"},
            "missing_in_depends_on_blocks": {
                "ProductBlockOneForTest": {
                    "missing_product_blocks_in_db": {"SubBlockOneForTest"},
                    "missing_resource_types_in_db": {"int_field", "list_field", "str_field"},
                },
                "SubBlockOneForTest": {"missing_resource_types_in_db": {"int_field", "str_field"}},
            },
            "missing_product_blocks_in_db": {"ProductBlockOneForTest"},
        }
    }


def test_from_other_lifecycle_abstract(test_product_one):
    class AbstractProductBlockOneForTestInactive(ProductBlockModel, product_block_name="ProductBlockOneForTest"):
        str_field: Optional[str] = None
        list_field: List[int] = Field(default_factory=list)

    class AbstractProductBlockOneForTestProvisioning(
        AbstractProductBlockOneForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        str_field: Optional[str] = None
        list_field: List[int]

    class AbstractProductBlockOneForTest(
        AbstractProductBlockOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        str_field: str
        list_field: List[int]

    class ProductBlockOneForTestInactive(
        AbstractProductBlockOneForTestInactive, product_block_name="ProductBlockOneForTest"
    ):
        str_field: Optional[str] = None
        list_field: List[int] = Field(default_factory=list)
        int_field: Optional[int] = None

    class ProductBlockOneForTestProvisioning(
        ProductBlockOneForTestInactive,
        AbstractProductBlockOneForTestProvisioning,
        lifecycle=[SubscriptionLifecycle.PROVISIONING],
    ):
        str_field: Optional[str] = None
        list_field: List[int]
        int_field: int

    class ProductBlockOneForTest(
        ProductBlockOneForTestProvisioning, AbstractProductBlockOneForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        str_field: str
        list_field: List[int]
        int_field: int

    block = ProductBlockOneForTestInactive.new(subscription_id=uuid4())
    assert isinstance(block, ProductBlockOneForTestInactive)

    block.int_field = 1
    block.str_field = "bla"
    block.list_field = [1]

    active_block = ProductBlockOneForTest._from_other_lifecycle(block, SubscriptionLifecycle.ACTIVE, uuid4())

    assert isinstance(active_block, AbstractProductBlockOneForTest)
    assert isinstance(active_block, ProductBlockOneForTest)
    assert active_block.db_model == block.db_model


def test_from_other_lifecycle_sub(test_product_one, test_product_block_one, test_product_sub_block_one):
    SubBlockOneForTestInactive, _, SubBlockOneForTest = test_product_sub_block_one
    ProductBlockOneForTestInactive, _, ProductBlockOneForTest = test_product_block_one
    subscription_id = uuid4()

    block = ProductBlockOneForTestInactive.new(
        subscription_id=subscription_id, int_field=1, str_field="bla", list_field=[1]
    )
    block.sub_block = SubBlockOneForTestInactive.new(subscription_id=subscription_id, int_field=1, str_field="bla")
    block.sub_block_2 = SubBlockOneForTestInactive.new(subscription_id=subscription_id, int_field=1, str_field="bla")
    block.sub_block_list = [
        SubBlockOneForTestInactive.new(subscription_id=subscription_id, int_field=1, str_field="bla")
    ]

    assert isinstance(block, ProductBlockOneForTestInactive)

    active_block = ProductBlockOneForTest._from_other_lifecycle(block, SubscriptionLifecycle.ACTIVE, uuid4())

    assert isinstance(active_block, ProductBlockOneForTest)
    assert isinstance(active_block.sub_block, SubBlockOneForTest)
    assert isinstance(active_block.sub_block_2, SubBlockOneForTest)
    assert isinstance(active_block.sub_block_list[0], SubBlockOneForTest)
    assert active_block.db_model == block.db_model
    assert active_block.sub_block.db_model == block.sub_block.db_model
    assert active_block.sub_block_2.db_model == block.sub_block_2.db_model
    assert active_block.sub_block_list[0].db_model == block.sub_block_list[0].db_model
