import pytest

from orchestrator.domain.base import ProductBlockModel
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
