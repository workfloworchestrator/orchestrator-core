from unittest import mock

from pydantic import computed_field

from orchestrator.domain import SubscriptionModel
from orchestrator.domain.base import DomainModel
from orchestrator.domain.context_cache import cache_subscription_models


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


def spy_get_subscription():
    # Spy on the _get_subscription method to observe the number of queries
    return mock.patch.object(
        SubscriptionModel,
        "_get_subscription",
        spec=SubscriptionModel._get_subscription,
        side_effect=SubscriptionModel._get_subscription,
    )


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


def test_serializable_property_with_cache_subscription_models(
    generic_subscription_1, generic_subscription_2, generic_product_type_1, generic_product_type_2, test_product_model
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

    class TestProduct(SubscriptionModel):
        @computed_field  # type: ignore
        @property
        def title(self) -> str:
            subscription1 = GenericProductOne.from_subscription(generic_subscription_1)
            subscription2 = GenericProductTwo.from_subscription(generic_subscription_2)
            return f"{subscription1.description} {subscription1.pb_2.rt_2} - {subscription2.description} {subscription2.pb_3.rt_2}"

        @computed_field  # type: ignore
        @property
        def foobar(self) -> str:
            subscription1 = GenericProductOne.from_subscription(generic_subscription_1)
            return f"{subscription1.description} {subscription1.pb_2.rt_2}"

    model = TestProduct(int_field=123, product=test_product_model, customer_id="")

    # when

    with spy_get_subscription() as mock_get_subscription_no_cache:
        actual_result_no_cache = model.model_dump(include=["title", "foobar"])

    with (
        spy_get_subscription() as mock_get_subscription_with_cache,
        cache_subscription_models(),  # <- cache enabled this time
    ):
        actual_result_with_cache = model.model_dump(include=["title", "foobar"])

    # then

    expected_result = {
        "title": "Generic Subscription One 42 - Generic Subscription Two 42",
        "foobar": "Generic Subscription One 42",
    }
    assert actual_result_no_cache == expected_result
    assert actual_result_with_cache == expected_result

    actual_calls_no_cache = sorted(mock_get_subscription_no_cache.mock_calls)
    expected_calls_no_cache = sorted(
        [
            mock.call(generic_subscription_1),
            mock.call(generic_subscription_1),
            mock.call(generic_subscription_2),
        ]
    )
    assert actual_calls_no_cache == expected_calls_no_cache

    actual_calls_with_cache = sorted(mock_get_subscription_with_cache.mock_calls)
    expected_calls_with_cache = sorted(
        [
            mock.call(generic_subscription_1),  # Queried once instead of twice
            mock.call(generic_subscription_2),
        ]
    )
    assert actual_calls_with_cache == expected_calls_with_cache
