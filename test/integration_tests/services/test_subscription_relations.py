# Copyright 2019-2026 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest

from orchestrator.core.db import SubscriptionTable, db
from orchestrator.core.domain.base import SubscriptionModel
from orchestrator.core.services.subscription_relations import get_depends_on_subscriptions, get_in_use_by_subscriptions
from orchestrator.core.services.subscriptions import (
    query_depends_on_subscriptions,
    query_in_use_by_subscriptions,
    select_depends_on_subscriptions,
    select_in_use_by_subscriptions,
)
from orchestrator.core.types import SubscriptionLifecycle


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


@pytest.mark.parametrize(
    ("legacy", "replacement", "subject"),
    [
        pytest.param(query_in_use_by_subscriptions, select_in_use_by_subscriptions, "sub_one", id="in_use_by"),
        pytest.param(query_depends_on_subscriptions, select_depends_on_subscriptions, "union", id="depends_on"),
    ],
)
def test_deprecated_query_helpers_match_select_helpers(
    legacy, replacement, subject, sub_one_subscription_1, product_sub_list_union_subscription_1
):
    subscription_id = {
        "sub_one": sub_one_subscription_1.subscription_id,
        "union": product_sub_list_union_subscription_1,
    }[subject]

    with pytest.warns(DeprecationWarning, match="will be removed in 6.0.0"):
        legacy_ids = {sub.subscription_id for sub in legacy(subscription_id).all()}

    expected_ids = set(
        db.session.scalars(replacement(subscription_id).with_only_columns(SubscriptionTable.subscription_id))
    )
    assert expected_ids
    assert legacy_ids == expected_ids
