import pytest

from orchestrator.domain.base import ProductBlockModel
from orchestrator.domain.lifecycle import validate_subscription_lifecycle
from orchestrator.settings import LifecycleValidationMode
from orchestrator.types import SubscriptionLifecycle


@pytest.fixture
def setup():
    class SubBlockInactive(ProductBlockModel, product_block_name="SubBlock"):
        int_field: int | None = None

    class SubBlockProvisioning(SubBlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        int_field: int

    class MainBlockInactive(ProductBlockModel, product_block_name="MainBlock"):
        sub_block1: SubBlockInactive
        sub_block2: SubBlockInactive

    yield SubBlockInactive, SubBlockProvisioning, MainBlockInactive


def test_invalid_lifecycle_status(setup):
    SubBlockInactive, SubBlockProvisioning, MainBlockInactive = setup

    expected_error = (
        r"lifecycle status of the type for the field: "
        r"sub_block1, SubBlockProvisioning \(based on SubBlockInactive\) is not suitable for the "
        r"lifecycle status \(provisioning\) of this model"
    )
    with pytest.raises(AssertionError, match=expected_error):

        class MainBlockProvisioning(MainBlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
            sub_block1: SubBlockInactive  # invalid lifecycle
            sub_block2: SubBlockInactive  # invalid lifecycle but currently not mentioned in the error


def test_invalid_lifecycle_status_union(setup):
    SubBlockInactive, SubBlockProvisioning, MainBlockInactive = setup

    expected_error = (
        r"The lifecycle status of the type for the field: "
        r"sub_block2, SubBlockProvisioning \(based on SubBlockInactive\) is not suitable for the "
        r"lifecycle status \(provisioning\) of this model"
    )
    with pytest.raises(AssertionError, match=expected_error):

        class MainBlockProvisioning(MainBlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
            sub_block1: SubBlockProvisioning
            sub_block2: SubBlockProvisioning | SubBlockInactive  # first lifecycle is valid, second is not


def test_validate_subscription_lifecycle_valid(sub_one_subscription_1, caplog):
    # Test create with wrong lifecycle, we can create

    with caplog.at_level("WARNING"):
        validate_subscription_lifecycle(sub_one_subscription_1, validation_mode=LifecycleValidationMode.STRICT)
        # Assert no warnings or errors were logged
        assert not caplog.records


def test_validate_subscription_lifecycle_invalid(sub_one_subscription_1):
    # Test create with wrong lifecycle, we can create
    sub_one_subscription_1.status = "provisioning"

    with pytest.raises(
        ValueError,
        match=r"Subscription of type .* should use .* for lifecycle status '.*'",
    ):
        validate_subscription_lifecycle(sub_one_subscription_1, validation_mode=LifecycleValidationMode.STRICT)
