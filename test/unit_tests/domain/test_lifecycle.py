import pytest

from orchestrator.domain.base import ProductBlockModel
from orchestrator.domain.lifecycle import validate_subscription_model_product_type
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


@pytest.mark.parametrize("lifecycle_validation_mode", [LifecycleValidationMode.STRICT, LifecycleValidationMode.LOOSE])
def test_validate_subscription_model_product_type_correct_type(
    sub_one_subscription_1, caplog, lifecycle_validation_mode
):
    """Test that a subscription model has been instantiated with the correct product type class for its lifecycle status."""

    with caplog.at_level("WARNING"):
        validate_subscription_model_product_type(sub_one_subscription_1, validation_mode=lifecycle_validation_mode)
        assert not caplog.records


@pytest.mark.parametrize(
    "lifecycle_status,expected_error",
    [
        (SubscriptionLifecycle.INITIAL, r"Subscription of type .* should use .* for lifecycle status 'initial'"),
        (SubscriptionLifecycle.MIGRATING, r"Subscription of type .* should use .* for lifecycle status 'migrating'"),
        (SubscriptionLifecycle.DISABLED, r"Subscription of type .* should use .* for lifecycle status 'disabled'"),
        (SubscriptionLifecycle.TERMINATED, r"Subscription of type .* should use .* for lifecycle status 'terminated'"),
        (
            SubscriptionLifecycle.PROVISIONING,
            r"Subscription of type .* should use .* for lifecycle status 'provisioning'",
        ),
    ],
)
def test_validate_subscription_model_product_type_invalid_lifecycle_error(
    sub_one_subscription_1, lifecycle_status, expected_error
):
    """Test with lifecycles that does not match the subscription type."""
    sub_one_subscription_1.status = lifecycle_status

    with pytest.raises(
        ValueError,
        match=expected_error,
    ):
        validate_subscription_model_product_type(sub_one_subscription_1, validation_mode=LifecycleValidationMode.STRICT)


def test_warning_logged_on_invalid_lifecycle(sub_one_subscription_1, caplog):
    """Test that a warning is logged when the lifecycle status does not match the subscription type and validation mode is LOOSE."""
    sub_one_subscription_1.status = SubscriptionLifecycle.PROVISIONING  # actual status is 'active'

    with caplog.at_level("WARNING"):
        validate_subscription_model_product_type(sub_one_subscription_1, validation_mode=LifecycleValidationMode.LOOSE)

    # Assert that a warning was logged
    assert any(record.levelname == "WARNING" for record in caplog.records)
