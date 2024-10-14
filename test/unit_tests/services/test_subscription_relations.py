from orchestrator.db import db
from orchestrator.domain.base import SubscriptionModel
from orchestrator.services.subscription_relations import get_depends_on_subscriptions, get_in_use_by_subscriptions
from orchestrator.types import SubscriptionLifecycle


def terminate_subscription(subscription_id):
    subscription = SubscriptionModel.from_subscription(subscription_id)
    terminated_subscription = SubscriptionModel.from_other_lifecycle(subscription, SubscriptionLifecycle.TERMINATED)
    terminated_subscription.save()
    db.session.commit()
    return terminated_subscription


async def test_get_in_use_by_subscriptions(
    sub_one_subscription_1,
    sub_two_subscription_1,
    product_sub_list_union_subscription_1,
    sub_list_union_overlap_subscription_1,
):
    # when
    subscription_ids = [sub_one_subscription_1.subscription_id, sub_two_subscription_1.subscription_id]

    terminate_subscription(product_sub_list_union_subscription_1)
    terminate_subscription(sub_two_subscription_1.subscription_id)

    result = await get_in_use_by_subscriptions(subscription_ids, ())

    # then
    expected_result = [
        # sub_one_subscription_1 in_use_by_subscriptions
        sorted([product_sub_list_union_subscription_1, sub_list_union_overlap_subscription_1.subscription_id]),
        # sub_two_subscription_1 in_use_by_subscriptions
        [product_sub_list_union_subscription_1],
    ]

    assert [sorted([sub.subscription_id for sub in r_list]) for r_list in result] == expected_result


async def test_get_in_use_by_subscriptions_only_active(
    sub_one_subscription_1,
    sub_two_subscription_1,
    product_sub_list_union_subscription_1,
    sub_list_union_overlap_subscription_1,
):
    # when
    subscription_ids = [sub_one_subscription_1.subscription_id, sub_two_subscription_1.subscription_id]

    terminate_subscription(product_sub_list_union_subscription_1)
    terminate_subscription(sub_two_subscription_1.subscription_id)

    result = await get_in_use_by_subscriptions(subscription_ids, ("active",))

    # then
    expected_result = [
        # sub_one_subscription_1 in_use_by_subscriptions
        sorted(
            [
                sub_list_union_overlap_subscription_1.subscription_id,  # ACTIVE
            ]
        ),
        # sub_two_subscription_1 in_use_by_subscriptions - terminated
        [],
    ]

    assert [sorted([sub.subscription_id for sub in r_list]) for r_list in result] == expected_result


async def test_get_in_use_by_subscriptions_only_terminated(
    sub_one_subscription_1,
    sub_two_subscription_1,
    product_sub_list_union_subscription_1,
    sub_list_union_overlap_subscription_1,
):
    # when
    subscription_ids = [sub_one_subscription_1.subscription_id, sub_two_subscription_1.subscription_id]

    terminate_subscription(product_sub_list_union_subscription_1)
    terminate_subscription(sub_two_subscription_1.subscription_id)

    result = await get_in_use_by_subscriptions(subscription_ids, ("terminated",))

    # then
    expected_result = [
        # sub_one_subscription_1 in_use_by_subscriptions
        [product_sub_list_union_subscription_1],
        # sub_two_subscription_1 in_use_by_subscriptions - terminated
        [product_sub_list_union_subscription_1],
    ]

    assert [sorted([sub.subscription_id for sub in r_list]) for r_list in result] == expected_result


async def test_get_in_use_by_subscriptions_empty():
    # when
    subscription_ids = []

    result = await get_in_use_by_subscriptions(subscription_ids, ())

    # then
    expected_result = []

    assert result == expected_result


async def test_get_depends_on_subscriptions(
    sub_one_subscription_1,
    sub_two_subscription_1,
    product_sub_list_union_subscription_1,
    sub_list_union_overlap_subscription_1,
):
    # when
    subscription_ids = [product_sub_list_union_subscription_1, sub_list_union_overlap_subscription_1.subscription_id]

    result = await get_depends_on_subscriptions(subscription_ids, ())

    # then
    expected_result = [
        # product_sub_list_union_subscription_1 in_use_by_subscriptions
        sorted([sub_two_subscription_1.subscription_id, sub_one_subscription_1.subscription_id]),
        # sub_list_union_overlap_subscription_1 in_use_by_subscriptions
        [sub_one_subscription_1.subscription_id],
    ]

    assert [sorted([sub.subscription_id for sub in r_list]) for r_list in result] == expected_result


async def test_get_depends_on_subscriptions_only_active(
    sub_one_subscription_1,
    sub_two_subscription_1,
    product_sub_list_union_subscription_1,
    sub_list_union_overlap_subscription_1,
):
    # when
    subscription_ids = [product_sub_list_union_subscription_1, sub_list_union_overlap_subscription_1.subscription_id]
    terminate_subscription(product_sub_list_union_subscription_1)
    terminate_subscription(sub_two_subscription_1.subscription_id)

    result = await get_depends_on_subscriptions(subscription_ids, ("active",))

    # then
    expected_result = [
        # product_sub_list_union_subscription_1 in_use_by_subscriptions - terminated
        [sub_one_subscription_1.subscription_id],
        # sub_list_union_overlap_subscription_1 in_use_by_subscriptions
        [sub_one_subscription_1.subscription_id],
    ]

    assert [sorted([sub.subscription_id for sub in r_list]) for r_list in result] == expected_result


async def test_get_depends_on_subscriptions_only_terminated(
    sub_one_subscription_1,
    sub_two_subscription_1,
    product_sub_list_union_subscription_1,
    sub_list_union_overlap_subscription_1,
):
    # when
    subscription_ids = [product_sub_list_union_subscription_1, sub_list_union_overlap_subscription_1.subscription_id]
    terminate_subscription(product_sub_list_union_subscription_1)
    terminate_subscription(sub_two_subscription_1.subscription_id)

    result = await get_depends_on_subscriptions(subscription_ids, ("terminated",))

    # then
    expected_result = [
        # product_sub_list_union_subscription_1 in_use_by_subscriptions - terminated
        sorted(
            [
                sub_two_subscription_1.subscription_id,  # TERMINATED
                # sub_one_subscription_1.subscription_id # ACTIVE
            ]
        ),
        # sub_list_union_overlap_subscription_1 in_use_by_subscriptions sub_one_subscription_1
        [],
    ]

    assert [sorted([sub.subscription_id for sub in r_list]) for r_list in result] == expected_result


async def test_get_depends_on_subscriptions_empty():
    # when
    subscription_ids = []

    result = await get_depends_on_subscriptions(subscription_ids, ())

    # then
    expected_result = []

    assert result == expected_result
