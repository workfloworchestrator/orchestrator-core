from datetime import datetime
from unittest import mock
from uuid import uuid4

import pytest
import pytz
from dirty_equals import IsUUID
from pydantic import BaseModel, Field, ValidationError, conlist
from sqlalchemy import func, select
from sqlalchemy.exc import NoResultFound

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
    SubscriptionModel,
)
from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.types import SubscriptionLifecycle
from test.unit_tests.fixtures.products.product_blocks.product_block_list_nested import (
    ProductBlockListNestedForTestInactive,
)
from test.unit_tests.fixtures.products.product_blocks.product_block_one import DummyEnum


def get_one_relation(depends_on_id):
    return db.session.scalars(
        select(SubscriptionInstanceRelationTable).where(
            SubscriptionInstanceRelationTable.depends_on_id == depends_on_id
        )
    ).one()


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


@pytest.fixture
def clean_registry():
    with mock.patch.dict(SUBSCRIPTION_MODEL_REGISTRY):
        yield


def test_subscription_model_registry(clean_registry):
    """Test the behavior of the subscription model registry."""

    # This is a Product Block model that should not be registered
    # reason: it has a field that is itself Pydantic BaseModel
    class ForbiddenProductBlock(ProductBlockModel, product_block_name="ForbiddenProductBlock"):
        ordinary_str: str
        ordinary_int: list[int]
        pydantic_block: BaseModel

    # This is a Subscription model that should not be registered
    # reason: it has an invalid Product Block model
    class ForbiddenSubscription(SubscriptionModel, is_base=True):
        forbidden_block: ForbiddenProductBlock

    # This is a Product Block model that should not be registered
    # reason: it is a direct subclass of Pydantic BaseModel
    # note: subclassing BaseModel won't allow `product_block_name` to be passed
    class ToxicProductBlock(BaseModel):
        ordinary_str: str
        ordinary_int: list[int]

    # This is a Subscription model that should not be registered
    # reason: it has an invalid Product Block model
    class ToxicSubscription(SubscriptionModel, is_base=True):
        toxic_block: ToxicProductBlock

    # This is a Product Block model that should not be registered
    # reason: it contains a direct subclass of Pydantic BaseModel
    class PoisonedProductBlock(ProductBlockModel, product_block_name="PoisonedProductBlock"):
        ordinary_str: str
        ordinary_int_list: list[int]
        toxic_block: ToxicProductBlock

    # This is a Subscription model that should not be registered
    # reason: because it has an invalid Product Block model
    class PoisonedSubscription(SubscriptionModel, is_base=True):
        poisoned_block: PoisonedProductBlock

    # This is a Product Block model that should not be registered
    # reason: it has an invalid Product Block model
    class CursedProductBlock(ProductBlockModel, product_block_name="CursedProductBlock"):
        ordinary_str: str
        ordinary_int_list: list[int]
        poisoned_block: PoisonedProductBlock

    # This is a Subscription model that should not be registered
    # reason: it has an invalid Product Block model
    class CursedSubscription(SubscriptionModel, is_base=True):
        cursed_block: CursedProductBlock

    # This is a Product Block model that should be registered
    # reason: it only uses ordinary fields
    class CommonProductBlock(ProductBlockModel, product_block_name="CommonProductBlock"):
        ordinary_str: str
        ordinary_int_list: list[int]

    # This is a Subscription model that should be registered
    # reason: it has a valid Product Block model
    class CommonSubscription(SubscriptionModel, is_base=True):
        common_block: CommonProductBlock

    # This is a Product Block model that should be registered
    # reason: it contains a valid Product Block model
    class UncommonProductBlock(ProductBlockModel, product_block_name="UncommonProductBlock"):
        ordinary_str: str
        ordinary_int_list: list[int]
        common_block: CommonProductBlock

    # This is a Subscription model that should be registered
    # reason: it contains a valid Product Block model
    class UncommonSubscription(SubscriptionModel, is_base=True):
        uncommon_block: UncommonProductBlock

    # This is a Subscription model that should not be registered
    # reason: it has multiple invalid Product Block models
    class HauntedSubscription(SubscriptionModel, is_base=True):
        forbidden_field: BaseModel
        forbidden_block: ForbiddenProductBlock
        toxic_block: ToxicProductBlock
        poisoned_block: PoisonedProductBlock
        cursed_block: CursedProductBlock
        common_block: CommonProductBlock
        uncommon_block: UncommonProductBlock

    # List of invalid Subscription models that should raise TypeError
    invalid_subscriptions = {
        "forbidden_subscription": ForbiddenSubscription,
        "toxic_subscription": ToxicSubscription,
        "poisoned_subscription": PoisonedSubscription,
        "cursed_subscription": CursedSubscription,
        "haunted_subscription": HauntedSubscription,
    }

    # Error will mention that the model can't be BaseModel or a direct subclass
    for name, model in invalid_subscriptions.items():
        err = r"(not be BaseModel|not be a direct subclass of BaseModel)"
        with pytest.raises(TypeError, match=err):
            SUBSCRIPTION_MODEL_REGISTRY.update({name: model})

    # List of valid Subscription models that should register successfully
    valid_subscriptions = {
        "common_subscription": CommonSubscription,
        "uncommon_subscription": UncommonSubscription,
    }

    # These must register successfully when done individually
    for name, model in valid_subscriptions.items():
        try:
            SUBSCRIPTION_MODEL_REGISTRY.update({name: model})
        except TypeError:
            pytest.fail(f"Subscription {model.__name__} registered as " f"{name} should be valid but raised TypeError.")

    # Test every signature the update method takes and reset using clear
    try:
        SUBSCRIPTION_MODEL_REGISTRY.update(valid_subscriptions)
        SUBSCRIPTION_MODEL_REGISTRY.clear()
    except TypeError:
        pytest.fail(f"{valid_subscriptions} failed to register using the mapping signature of the update method.")
    try:
        SUBSCRIPTION_MODEL_REGISTRY.update(valid_subscriptions.items())
        SUBSCRIPTION_MODEL_REGISTRY.clear()
    except TypeError:
        pytest.fail(f"{valid_subscriptions} failed to register using the iterable of tuples signature.")
    try:
        SUBSCRIPTION_MODEL_REGISTRY.update(**{name: model})
        SUBSCRIPTION_MODEL_REGISTRY.clear()
    except TypeError:
        pytest.fail(f"{valid_subscriptions} failed to register using the keyword arguments signature.")
    try:
        SUBSCRIPTION_MODEL_REGISTRY.update(
            {"common_subscription": CommonSubscription}, uncommon_subscription=UncommonSubscription
        )
        SUBSCRIPTION_MODEL_REGISTRY.clear()
    except TypeError:
        pytest.fail(f"{valid_subscriptions} failed to register using the mixed mapping and kwargs signature.")
    try:
        SUBSCRIPTION_MODEL_REGISTRY.update(
            [("common_subscription", CommonSubscription)], uncommon_subscription=UncommonSubscription
        )
        SUBSCRIPTION_MODEL_REGISTRY.clear()
    except TypeError:
        pytest.fail(
            f"{valid_subscriptions} failed to register using the mixed iterable of tuples and kwargs signature."
        )


def test_product_block_one_nested(
    test_product_model_nested, test_product_type_one_nested, test_product_block_one_nested
):
    """Test the behavior of nesting (self-referencing) product blocks.

    Notes:
        - nesting only works when each block is attached to a different subscription

    """
    ProductTypeOneNestedForTestInactive, _, ProductTypeOneNestedForTest = test_product_type_one_nested
    ProductBlockOneNestedForTestInactive, _, _ = test_product_block_one_nested
    customer_id = str(uuid4())

    def create_subscription(*, int_value, sub_block=None):
        subscription = ProductTypeOneNestedForTestInactive.from_product_id(
            product_id=test_product_model_nested.product_id, customer_id=customer_id, insync=True
        )
        subscription.block = ProductBlockOneNestedForTestInactive.new(
            subscription_id=subscription.subscription_id, int_field=int_value, sub_block=sub_block
        )
        subscription = SubscriptionModel.from_other_lifecycle(subscription, SubscriptionLifecycle.ACTIVE)
        subscription.save()
        db.session.commit()
        return subscription

    def assert_int_values(subscription, *, level1, level2, level3):
        block = subscription.block
        actual_values = (block.int_field, block.sub_block.int_field, block.sub_block.sub_block.int_field)
        assert (level1, level2, level3) == actual_values
        assert block.sub_block.sub_block.sub_block is None

    # Create productblock 30 that will be nested in block 20
    subscription_30 = create_subscription(int_value=30)

    # Create productblock 20 that refers to block 30, and will be nested in block 10
    subscription_20 = create_subscription(int_value=20, sub_block=subscription_30.block)

    # Create productblock 10 that refers to block 20
    subscription_10 = create_subscription(int_value=10, sub_block=subscription_20.block)

    # Load block 10 and verify the nested blocks
    subscription_10 = ProductTypeOneNestedForTest.from_subscription(subscription_10.subscription_id)
    assert_int_values(subscription_10, level1=10, level2=20, level3=30)

    # Load block 20 and verify the nested block
    subscription_20 = ProductTypeOneNestedForTest.from_subscription(subscription_20.subscription_id)
    assert subscription_20.block.int_field == 20
    assert subscription_20.block.sub_block.int_field == 30
    assert subscription_20.block.sub_block.sub_block is None

    # Create productblock 11 that also refers to block 20
    subscription_11 = create_subscription(int_value=11, sub_block=subscription_20.block)

    # Load block 11 and verify the nested blocks
    subscription_11 = ProductTypeOneNestedForTest.from_subscription(subscription_11.subscription_id)
    assert_int_values(subscription_11, level1=11, level2=20, level3=30)

    # (again) Load block 10 and verify the nested blocks are same as before
    subscription_10 = ProductTypeOneNestedForTest.from_subscription(subscription_10.subscription_id)
    assert_int_values(subscription_10, level1=10, level2=20, level3=30)

    # Below part might not be interesting to test, or better off in a separate testcase.
    # I was just curious what happens when we delete things.

    # Remove block 20 from block 10
    subscription_10.block.sub_block = None
    subscription_10.save()
    db.session.commit()

    # Load block 10 and verify the nested block is removed
    subscription_10 = ProductTypeOneNestedForTest.from_subscription(subscription_10.subscription_id)
    assert subscription_10.block.int_field == 10
    assert subscription_10.block.sub_block is None

    # Load block 11 and verify the nested blocks still exist
    subscription_11 = ProductTypeOneNestedForTest.from_subscription(subscription_11.subscription_id)
    assert_int_values(subscription_11, level1=11, level2=20, level3=30)


def test_product_block_list_nested(test_product_model_list_nested, test_product_type_list_nested):
    """Test the behavior of nesting (self-referencing) a list of product blocks.

    Notes:
        - nesting only works when each block is attached to a different subscription

    """
    ProductTypeListNestedForTestInactive, _, ProductTypeListNestedForTest = test_product_type_list_nested

    customer_id = str(uuid4())

    def create_subscription(*, int_value, sub_blocks=()):
        subscription = ProductTypeListNestedForTestInactive.from_product_id(
            product_id=test_product_model_list_nested.product_id, customer_id=customer_id, insync=True
        )
        subscription.block = ProductBlockListNestedForTestInactive.new(
            subscription_id=subscription.subscription_id, int_field=int_value, sub_block_list=list(sub_blocks)
        )
        subscription = SubscriptionModel.from_other_lifecycle(subscription, SubscriptionLifecycle.ACTIVE)
        subscription.save()
        db.session.commit()
        return subscription

    def assert_int_values(subscription, *, level1, level2, level3):
        block = subscription.block
        assert level1 == block.int_field
        assert level2 == sorted(l2.int_field for l2 in block.sub_block_list)
        assert level3 == sorted(l3.int_field for l2 in block.sub_block_list for l3 in l2.sub_block_list)

    # Create productblocks 30 and 31 that will both be nested in block 20 and 21
    subscription_30 = create_subscription(int_value=30)
    subscription_31 = create_subscription(int_value=31)

    # Create productblocks 20 and 21 that both
    # - refer to blocks 30 and 31
    # - will be nested in blocks 10 and 11
    subscription_20 = create_subscription(int_value=20, sub_blocks=(subscription_30.block, subscription_31.block))
    subscription_21 = create_subscription(int_value=21, sub_blocks=(subscription_30.block, subscription_31.block))

    # Create productblocks 10 and 11 that both refer to blocks 20 and 21
    subscription_10 = create_subscription(int_value=10, sub_blocks=(subscription_20.block, subscription_21.block))
    subscription_11 = create_subscription(int_value=11, sub_blocks=(subscription_20.block, subscription_21.block))

    # Load blocks 10 and 11 and verify the nested blocks
    subscription_10 = ProductTypeListNestedForTest.from_subscription(subscription_10.subscription_id)
    subscription_11 = ProductTypeListNestedForTest.from_subscription(subscription_11.subscription_id)
    assert_int_values(subscription_10, level1=10, level2=[20, 21], level3=[30, 30, 31, 31])
    assert_int_values(subscription_11, level1=11, level2=[20, 21], level3=[30, 30, 31, 31])

    # Assert that blocks at deepest level don't refer to any other blocks
    assert subscription_10.block.sub_block_list[0].sub_block_list[0].sub_block_list == []
    assert subscription_11.block.sub_block_list[1].sub_block_list[1].sub_block_list == []

    # Load block 20 and verify nested blocks
    subscription_20 = ProductTypeListNestedForTest.from_subscription(subscription_20.subscription_id)
    assert_int_values(subscription_20, level1=20, level2=[30, 31], level3=[])

    # Create productblock 32 and nest it in block 20 (but not 21!)
    subscription_32 = create_subscription(int_value=32)
    subscription_20.block.sub_block_list.append(subscription_32.block)
    subscription_20.save()
    db.session.commit()

    # (again) Load blocks 10 and 11 and verify block 32 is present once
    subscription_10 = ProductTypeListNestedForTest.from_subscription(subscription_10.subscription_id)
    subscription_11 = ProductTypeListNestedForTest.from_subscription(subscription_11.subscription_id)
    assert_int_values(subscription_10, level1=10, level2=[20, 21], level3=[30, 30, 31, 31, 32])
    assert_int_values(subscription_11, level1=11, level2=[20, 21], level3=[30, 30, 31, 31, 32])


def test_lifecycle(test_product_model, test_product_type_one, test_product_block_one):
    ProductBlockOneForTestInactive, _, _ = test_product_block_one
    ProductTypeOneForTestInactive, _, _ = test_product_type_one
    subscription_id = uuid4()

    # Test create with wrong lifecycle, we can create
    with pytest.raises(ValueError, match=r"is not valid for status active"):
        ProductTypeOneForTestInactive(
            product=test_product_model,
            customer_id=str(uuid4()),
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
        customer_id=str(uuid4()),
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
        customer_id=str(uuid4()),
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
            enum_field=DummyEnum.FOO,
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
        customer_id=str(uuid4()),
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
            enum_field=DummyEnum.FOO,
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
            customer_id=str(uuid4()),
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
                enum_field=DummyEnum.FOO,
                sub_block=SubBlockOneForTestProvisioning.new(subscription_id=subscription_id, int_field=3),
                sub_block_2=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            ),
            status=SubscriptionLifecycle.ACTIVE,
            test_fixed_input=False,
        )

    # Works with right lifecycle
    product_type = ProductTypeOneForTestProvisioning(
        product=test_product_model,
        customer_id=str(uuid4()),
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
            enum_field=DummyEnum.FOO,
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
        customer_id=str(uuid4()),
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
            enum_field=DummyEnum.FOO,
            sub_block=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.INITIAL,
        test_fixed_input=False,
    )

    ProductTypeOneForTestInactive(
        product=test_product_model,
        customer_id=str(uuid4()),
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
        customer_id=str(uuid4()),
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
            enum_field=DummyEnum.FOO,
            sub_block=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.PROVISIONING,
        test_fixed_input=False,
    )

    ProductTypeOneForTest(
        product=test_product_model,
        customer_id=str(uuid4()),
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
            enum_field=DummyEnum.FOO,
            sub_block=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.ACTIVE,
        test_fixed_input=False,
    )

    ProductTypeOneForTest(
        product=test_product_model,
        customer_id=str(uuid4()),
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
            enum_field=DummyEnum.FOO,
            sub_block=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
            sub_block_2=SubBlockOneForTest.new(subscription_id=subscription_id, int_field=3, str_field=""),
        ),
        status=SubscriptionLifecycle.INITIAL,
        test_fixed_input=False,
    )

    with pytest.raises(
        ValidationError,
        match=(
            r"2 validation errors for SubBlockOneForTest\nint_field\n\s+Field required.+\n.+\nstr_field\n\s+Field required"
        ),  # Note: the . does not match newlines
    ):
        ProductTypeOneForTest(
            product=test_product_model,
            customer_id=str(uuid4()),
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

    with pytest.raises(
        ValidationError,
        match=r"1 validation error for ProductTypeOneForTest\nblock\n.+dictionary or instance of ProductBlockOneForTest",
    ):
        ProductTypeOneForTest(
            product=test_product_model,
            customer_id=str(uuid4()),
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
        ValidationError, match=r"1 validation error for ProductTypeOneForTest\nblock\n\s+Field required .+"
    ):
        ProductTypeOneForTest(
            product=test_product_model,
            customer_id=str(uuid4()),
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
        ValidationError, match=r"1 validation error for ProductTypeOneForTest\nblock\n\s+Field required .+"
    ):
        ProductTypeOneForTest(
            product=test_product_model,
            customer_id=str(uuid4()),
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
        str(uuid4()),
    )
    product_type.block = ProductBlockOneForTestInactive.new(
        subscription_id=product_type.subscription_id,
        sub_block_2=SubBlockOneForTestInactive.new(subscription_id=product_type.subscription_id),
    )

    # Does not work if constraints are not met
    with pytest.raises(
        ValidationError,
        match=r"int_field\n\s+Input should be a valid integer.+\n.+\nstr_field\n\s+Input should be a valid string",
    ):
        product_type = SubscriptionModel.from_other_lifecycle(product_type, SubscriptionLifecycle.ACTIVE)
    with pytest.raises(ValidationError, match=r"int_field\n\s+Input should be a valid integer"):
        product_type = SubscriptionModel.from_other_lifecycle(product_type, SubscriptionLifecycle.PROVISIONING)

    # Set first value
    product_type.block.int_field = 3
    product_type.block.sub_block.int_field = 3
    product_type.block.sub_block_2.int_field = 3
    product_type.block.sub_block_list = [SubBlockOneForTestInactive.new(subscription_id=product_type.subscription_id)]
    product_type.block.sub_block_list[0].int_field = 4
    product_type.block.list_field = [1]
    product_type.block.enum_field = DummyEnum.FOO

    # Does not work if constraints are not met
    with pytest.raises(ValidationError, match=r"str_field\n\s+Input should be a valid string"):
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
    expected_dict = product_type.model_dump()
    expected_dict["status"] = SubscriptionLifecycle.ACTIVE
    expected_dict["start_date"] = mock.ANY
    assert product_type_new.model_dump() == expected_dict
    assert isinstance(product_type_new.start_date, datetime)


def test_save_load(test_product_model, test_product_type_one, test_product_block_one, test_product_sub_block_one):
    SubBlockOneForTestInactive, SubBlockOneForTestProvisioning, SubBlockOneForTest = test_product_sub_block_one
    ProductBlockOneForTestInactive, ProductBlockOneForTestProvisioning, ProductBlockOneForTest = test_product_block_one
    ProductTypeOneForTestInactive, ProductTypeOneForTestProvisioning, ProductTypeOneForTest = test_product_type_one

    customer_id = str(uuid4())

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
        db.session.scalar(
            select(func.count())
            .select_from(SubscriptionInstanceValueTable)
            .join(SubscriptionInstanceValueTable.subscription_instance)
            .filter(SubscriptionInstanceTable.subscription_id == model.subscription_id)
        )
        == 1
    )

    assert model.model_dump() == {
        "block": {
            "int_field": None,
            "enum_field": None,
            "label": None,
            "list_field": [],
            "title": "TEST ProductBlockOneForTestInactive int_field=None",
            "name": "ProductBlockOneForTest",
            "str_field": "A",
            "sub_block": {
                "int_field": None,
                "label": None,
                "name": "SubBlockOneForTest",
                "str_field": None,
                "subscription_instance_id": IsUUID(),
                "owner_subscription_id": IsUUID(),
            },
            "sub_block_2": None,
            "sub_block_list": [],
            "owner_subscription_id": IsUUID(),
            "subscription_instance_id": IsUUID(),
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
        "subscription_id": IsUUID(),
        "test_fixed_input": False,
        "version": 1,
    }

    # Set first value
    model.block.int_field = 3
    model.block.enum_field = DummyEnum.FOO
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
    assert model.model_dump() | {"version": model.version + 1} == new_model.model_dump()

    # Second save also works as expected
    new_model.save()
    db.session.commit()

    latest_model = ProductTypeOneForTest.from_subscription(model.subscription_id)
    assert new_model.model_dump() == latest_model.model_dump()

    # Loading blocks also works
    block = ProductBlockOneForTest.from_db(model.block.subscription_instance_id)
    assert block.model_dump() == model.block.model_dump()


def test_update_constrained_lists(test_product_one, test_product_block_one):
    ProductBlockOneForTestInactive, _, _ = test_product_block_one

    class TestConListProductType(SubscriptionModel, is_base=True):
        saps: conlist(ProductBlockOneForTestInactive, min_length=1, max_length=4)

    # Creates
    ip = TestConListProductType.from_product_id(product_id=test_product_one, customer_id=str(uuid4()))
    ip.save()

    sap = ProductBlockOneForTestInactive.new(subscription_id=ip.subscription_id, int_field=3, str_field="")

    # Set new saps, removes old one
    ip.saps = [sap]

    ip.save()

    ip2 = TestConListProductType.from_subscription(ip.subscription_id)

    # Old default saps should not be saved
    assert ip.model_dump() == ip2.model_dump()

    # Test constraint
    with pytest.raises(ValidationError):
        ip.saps = []


def test_update_lists(test_product_one, test_product_block_one):
    ProductBlockOneForTestInactive, _, _ = test_product_block_one

    class TestListProductType(SubscriptionModel, is_base=True):
        saps: list[ProductBlockOneForTestInactive]

    # Creates
    ip = TestListProductType.from_product_id(product_id=test_product_one, customer_id=str(uuid4()))
    ip.save()

    sap = ProductBlockOneForTestInactive.new(subscription_id=ip.subscription_id, int_field=3, str_field="")

    # Set new saps
    ip.saps = [sap]

    ip.save()

    ip2 = TestListProductType.from_subscription(ip.subscription_id)

    # Old default saps should not be saved
    assert ip.model_dump() == ip2.model_dump()


def test_update_optional(test_product_one, test_product_block_one):
    ProductBlockOneForTestInactive, _, _ = test_product_block_one

    class TestListProductType(SubscriptionModel, is_base=True):
        sap: ProductBlockOneForTestInactive | None = None

    # Creates
    ip = TestListProductType.from_product_id(product_id=test_product_one, customer_id=str(uuid4()))
    ip.save()

    sap = ProductBlockOneForTestInactive.new(subscription_id=ip.subscription_id, int_field=3, str_field="")

    # Set new sap
    ip.sap = sap

    ip.save()

    ip2 = TestListProductType.from_subscription(ip.subscription_id)

    # Old default saps should not be saved
    assert ip.model_dump() == ip2.model_dump()


def test_generic_from_subscription(test_product_one, test_product_type_one):
    ProductTypeOneForTestInactive, _, _ = test_product_type_one

    ip = ProductTypeOneForTestInactive.from_product_id(product_id=test_product_one, customer_id=str(uuid4()))
    ip.save()

    model = SubscriptionModel.from_subscription(ip.subscription_id)

    assert isinstance(model, ProductTypeOneForTestInactive)


def test_label_is_saved(test_product_one, test_product_type_one):
    ProductTypeOneForTestInactive, _, _ = test_product_type_one

    test_model = ProductTypeOneForTestInactive.from_product_id(test_product_one, str(uuid4()))
    test_model.block.label = "My label"
    test_model.save()
    db.session.commit()
    instance_in_db = db.session.get(SubscriptionInstanceTable, test_model.block.subscription_instance_id)
    assert instance_in_db.label == "My label"


def test_domain_model_attrs_saving_loading(test_product_one, test_product_type_one, test_product_sub_block_one):
    SubBlockOneForTestInactive, _, _ = test_product_sub_block_one
    ProductTypeOneForTestInactive, _, _ = test_product_type_one

    test_model = ProductTypeOneForTestInactive.from_product_id(product_id=test_product_one, customer_id=str(uuid4()))
    test_model.block.sub_block_2 = SubBlockOneForTestInactive.new(subscription_id=test_model.subscription_id)
    test_model.block.sub_block_list = [SubBlockOneForTestInactive.new(subscription_id=test_model.subscription_id)]
    test_model.save()
    db.session.commit()

    def get_one_relation(depends_on_id):
        return db.session.scalars(
            select(SubscriptionInstanceRelationTable).where(
                SubscriptionInstanceRelationTable.depends_on_id == depends_on_id
            )
        ).one()

    relation = get_one_relation(test_model.block.sub_block.subscription_instance_id)
    assert relation.domain_model_attr == "sub_block"

    relation = get_one_relation(test_model.block.sub_block_2.subscription_instance_id)
    assert relation.domain_model_attr == "sub_block_2"

    relation = get_one_relation(test_model.block.sub_block_list[0].subscription_instance_id)
    assert relation.domain_model_attr == "sub_block_list"

    test_model_2 = ProductTypeOneForTestInactive.from_subscription(test_model.subscription_id)
    assert test_model == test_model_2


def test_removal_of_domain_attrs(test_product_one, test_product_type_one, test_product_sub_block_one):
    SubBlockOneForTestInactive, _, _ = test_product_sub_block_one
    ProductTypeOneForTestInactive, _, _ = test_product_type_one

    test_model = ProductTypeOneForTestInactive.from_product_id(product_id=test_product_one, customer_id=str(uuid4()))
    test_model.block.sub_block_2 = SubBlockOneForTestInactive.new(subscription_id=test_model.subscription_id)

    test_model.save()
    db.session.commit()
    relation = get_one_relation(test_model.block.sub_block.subscription_instance_id)
    relation.domain_model_attr = None
    db.session.commit()
    with pytest.raises(
        ValueError,
        match=r"block\.sub_block\n\s+Input should be a valid dictionary or instance of SubBlockOneForTestInactive.+",
    ):
        ProductTypeOneForTestInactive.from_subscription(test_model.subscription_id)


def test_simple_model_with_no_attrs(generic_subscription_1, generic_product_type_1):
    GenericProductOneInactive, GenericProductOne = generic_product_type_1
    model = GenericProductOne.from_subscription(subscription_id=generic_subscription_1)
    with pytest.raises(NoResultFound):
        get_one_relation(model.pb_1.subscription_instance_id)


def test_abstract_super_block(test_product_one, test_product_type_one, test_product_block_one_db):
    ProductTypeOneForTestInactive, ProductTypeOneForTestProvisioning, ProductTypeOneForTest = test_product_type_one

    class AbstractProductBlockOneForTestInactive(ProductBlockModel):
        str_field: str | None = None
        list_field: list[int] = Field(default_factory=list)

    class AbstractProductBlockOneForTestProvisioning(
        AbstractProductBlockOneForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        str_field: str | None = None
        list_field: list[int]

    class AbstractProductBlockOneForTest(
        AbstractProductBlockOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        str_field: str
        list_field: list[int]

    class ProductBlockOneForTestInactive(
        AbstractProductBlockOneForTestInactive, product_block_name="ProductBlockOneForTest"
    ):
        str_field: str | None = None
        list_field: list[int] = Field(default_factory=list)
        int_field: int | None = None

    class ProductBlockOneForTestProvisioning(
        ProductBlockOneForTestInactive,
        AbstractProductBlockOneForTestProvisioning,
        lifecycle=[SubscriptionLifecycle.PROVISIONING],
    ):
        str_field: str | None = None
        list_field: list[int]
        int_field: int

    class ProductBlockOneForTest(
        ProductBlockOneForTestProvisioning, AbstractProductBlockOneForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        str_field: str
        list_field: list[int]
        int_field: int

    class AbstractProductTypeOneForTestInactive(SubscriptionModel):
        block: AbstractProductBlockOneForTestInactive

    class AbstractProductTypeOneForTestProvisioning(AbstractProductTypeOneForTestInactive):
        block: AbstractProductBlockOneForTestProvisioning

    class AbstractProductTypeOneForTest(AbstractProductTypeOneForTestProvisioning):
        block: AbstractProductBlockOneForTest

    class ProductTypeOneForTestInactive(AbstractProductTypeOneForTestInactive, is_base=True):  # noqa: F811
        block: ProductBlockOneForTestInactive

    class ProductTypeOneForTestProvisioning(  # noqa: F811
        ProductTypeOneForTestInactive,
        AbstractProductTypeOneForTestProvisioning,
        lifecycle=[SubscriptionLifecycle.PROVISIONING],
    ):
        block: ProductBlockOneForTestProvisioning

    class ProductTypeOneForTest(  # noqa: F811
        ProductTypeOneForTestProvisioning, AbstractProductTypeOneForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        block: ProductBlockOneForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTest

    test_model = ProductTypeOneForTestInactive.from_product_id(product_id=test_product_one, customer_id=str(uuid4()))
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
    assert block.model_dump() == test_model.block.model_dump()
    assert isinstance(block, ProductBlockOneForTest)

    block = ProductBlockOneForTest.from_db(test_model.block.subscription_instance_id)
    assert block.model_dump() == test_model.block.model_dump()
    assert isinstance(block, ProductBlockOneForTest)


def test_subscription_instance_list():
    def custom_conlist(t):
        return conlist(t, min_length=1, max_length=2)

    class Model(BaseModel):
        list_field: custom_conlist(int)

    with pytest.raises(ValidationError):
        Model(list_field=["a"])

    Model(list_field=[1])


def test_diff_in_db_empty(test_product_one, test_product_type_one):
    ProductTypeOneForTestInactive, _, _ = test_product_type_one

    assert ProductTypeOneForTestInactive.diff_product_in_database(test_product_one) == {}


def test_diff_in_db_when_no_fields(test_product_one, test_product_type_one):
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
                    "missing_resource_types_in_db": {"int_field", "list_field", "str_field", "enum_field"},
                },
                "SubBlockOneForTest": {"missing_resource_types_in_db": {"int_field", "str_field"}},
            },
            "missing_product_blocks_in_db": {"ProductBlockOneForTest"},
        }
    }


def test_from_other_lifecycle_abstract(test_product_one):
    class AbstractProductBlockOneForTestInactive(ProductBlockModel, product_block_name="ProductBlockOneForTest"):
        str_field: str | None = None
        list_field: list[int] = Field(default_factory=list)

    class AbstractProductBlockOneForTestProvisioning(
        AbstractProductBlockOneForTestInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        str_field: str | None = None
        list_field: list[int]

    class AbstractProductBlockOneForTest(
        AbstractProductBlockOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        str_field: str
        list_field: list[int]

    class ProductBlockOneForTestInactive(
        AbstractProductBlockOneForTestInactive, product_block_name="ProductBlockOneForTest"
    ):
        str_field: str | None = None
        list_field: list[int] = Field(default_factory=list)
        int_field: int | None = None

    class ProductBlockOneForTestProvisioning(
        ProductBlockOneForTestInactive,
        AbstractProductBlockOneForTestProvisioning,
        lifecycle=[SubscriptionLifecycle.PROVISIONING],
    ):
        str_field: str | None = None
        list_field: list[int]
        int_field: int

    class ProductBlockOneForTest(
        ProductBlockOneForTestProvisioning, AbstractProductBlockOneForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        str_field: str
        list_field: list[int]
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
        subscription_id=subscription_id, int_field=1, str_field="bla", list_field=[1], enum_field=DummyEnum.FOO
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


def test_property_with_tag(test_product_block_one, test_product_one, test_product_block_one_db):
    ProductBlockOneForTestInactive, _, _ = test_product_block_one

    block = ProductBlockOneForTestInactive.new(int_field=1, subscription_id=uuid4())

    assert block.title == "TEST ProductBlockOneForTestInactive int_field=1"


def test_subscription_save_list_with_zero_values(
    test_product_type_one, test_product_sub_block_one, product_one_subscription_1
):
    _, _, ProductTypeOneForTest = test_product_type_one

    subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
    subscription.block.list_field = [10, 0, 20, 30, 40, 0, 0]
    subscription.save()
    assert subscription.block.list_field == [10, 0, 20, 30, 40, 0, 0]

    subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
    assert subscription.block.list_field == [0, 0, 0, 10, 20, 30, 40]


def test_subscription_save_bool_list_with_false_values(
    test_product_type_one, test_product_sub_block_one, product_one_subscription_1
):
    _, _, ProductTypeOneForTest = test_product_type_one

    subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
    subscription.block.list_field = [True, False, True, False]
    subscription.save()
    assert subscription.block.list_field == [True, False, True, False]

    subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
    assert subscription.block.list_field == [False, False, True, True]
