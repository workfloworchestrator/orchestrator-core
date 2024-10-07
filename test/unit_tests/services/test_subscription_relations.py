from orchestrator.services.subscription_relations import get_depends_on_subscriptions, get_in_use_by_subscriptions


async def test_get_in_use_by_subscriptions(
    sub_one_subscription_1,
    sub_two_subscription_1,
    product_sub_list_union_subscription_1,
    sub_list_union_overlap_subscription_1,
):
    # when
    subscription_ids = [sub_one_subscription_1.subscription_id, sub_two_subscription_1.subscription_id]

    result = await get_in_use_by_subscriptions(subscription_ids, ())

    # then
    expected_result = [
        # sub_one_subscription_1 in_use_by_subscriptions
        sorted([product_sub_list_union_subscription_1, sub_list_union_overlap_subscription_1.subscription_id]),
        # sub_two_subscription_1 in_use_by_subscriptions
        [product_sub_list_union_subscription_1],
    ]

    assert [[sub.subscription_id for sub in r_list] for r_list in result] == expected_result


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

    assert [[sub.subscription_id for sub in r_list] for r_list in result] == expected_result
