from unittest import mock

from pydantic import computed_field

from orchestrator.domain import SubscriptionModel
from orchestrator.domain.base import DomainModel


def test_serializable_property():
    class DerivedDomainModel(DomainModel):
        @computed_field  # type: ignore[misc]
        @property
        def double_int_field(self) -> int:
            # This property is serialized
            return 2 * self.int_field

        @property
        def triple_int_field(self) -> int:
            # This property is not serialized
            return 3 * self.int_field

        int_field: int

    block = DerivedDomainModel(int_field=13)

    assert block.model_dump() == {"int_field": 13, "double_int_field": 26}


def test_inherited_serializable_property():
    class ProvisioningDomainModel(DomainModel):
        @computed_field  # type: ignore[misc]
        @property
        def double_int_field(self) -> int:
            return 2 * self.int_field

        @computed_field  # type: ignore[misc]
        @property
        def triple_int_field(self) -> int:
            return 3 * self.int_field

        int_field: int

    class ActiveDomainModel(ProvisioningDomainModel):
        @computed_field  # type: ignore[misc]
        @property
        def triple_int_field(self) -> int:
            # override the base property
            return 30 * self.int_field

    block = ActiveDomainModel(int_field=1)

    assert block.model_dump() == {"int_field": 1, "double_int_field": 2, "triple_int_field": 30}


def test_nested_serializable_property():
    """Ensure that nested serializable property's are included in the serialized model."""

    class DerivedDomainModel(DomainModel):
        @computed_field  # type: ignore[misc]
        @property
        def double_int_field(self) -> int:
            # This property is serialized
            return 2 * self.int_field

        int_field: int

    class ParentDomainModel(DomainModel):
        derived: DerivedDomainModel

    model = ParentDomainModel(derived=DerivedDomainModel(int_field=13))

    assert model.model_dump() == {"derived": {"int_field": 13, "double_int_field": 26}}


def test_subscription_model_in_serializable_property(
    generic_subscription_1, generic_subscription_2, generic_product_type_1, generic_product_type_2, monitor_sqlalchemy
):
    """Ensure that serializable properties can retrieve other SubscriptionModels without duplicate queries.

    While this works and will continue to work, is not recommended practice because reconstructing the entire
    subscription only to retrieve a few attributes is "overkill" and impacts peformance.
    Issue #899 has been created to track the design of a more efficient implementation.
    """
    _, GenericProductOne = generic_product_type_1
    _, GenericProductTwo = generic_product_type_2

    # One typical usecase -at SURF- is to define a computed 'title' for a product block based on details from
    # the owner subscription of a 'foreign' product block.
    #
    # For example:
    #
    # class PeerBlockProvisioning(PeerBlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    #     port: IpPeerPortBlock
    #
    #     @computed_field
    #     @property
    #     def title(self) -> str:
    #         sap = self.port.sap
    #         subscription = SubscriptionModel.from_subscription(sap.owner_subscription_id)
    #         return f"IP Peering on {subscription.description} vlan {sap.vlanrange}"
    #
    # Below we test a simplified but technically identical usecase.

    # given

    class DerivedDomainModel(DomainModel):
        @computed_field  # type: ignore[misc]
        @property
        def title(self) -> int:
            subscription1 = GenericProductOne.from_subscription(generic_subscription_1)
            subscription2 = GenericProductTwo.from_subscription(generic_subscription_2)
            return f"{subscription1.description} {subscription1.pb_2.rt_2} - {subscription2.description} {subscription2.pb_3.rt_2}"

        @computed_field
        @property
        def foobar(self) -> int:
            subscription1 = GenericProductOne.from_subscription(generic_subscription_1)
            return f"{subscription1.description} {subscription1.pb_2.rt_2}"

        int_field: int

    model = DerivedDomainModel(int_field=123)

    # when

    # Spy on the _get_subscription method to observe the number of queries
    with mock.patch.object(
        SubscriptionModel,
        "_get_subscription",
        spec=SubscriptionModel._get_subscription,
        side_effect=SubscriptionModel._get_subscription,
    ) as mock_get_subscription:
        actual_result = model.model_dump()

    # then

    expected_result = {
        "int_field": 123,
        "title": "Generic Subscription One 42 - Generic Subscription Two 42",
        "foobar": "Generic Subscription One 42",
    }
    assert actual_result == expected_result

    actual_calls = sorted(mock_get_subscription.mock_calls)
    expected_calls = sorted(
        [
            mock.call(generic_subscription_1),
            mock.call(generic_subscription_1),
            mock.call(generic_subscription_2),
        ]
    )
    assert actual_calls == expected_calls
