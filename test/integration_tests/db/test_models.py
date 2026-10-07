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

"""Integration tests for the lookup helpers on ProductBlockTable and SubscriptionTable."""

from uuid import UUID

import pytest
from sqlalchemy.exc import NoResultFound

from orchestrator.core.db import ProductBlockTable, SubscriptionTable, db


@pytest.mark.parametrize(
    ("finder", "key"),
    [
        pytest.param(ProductBlockTable.find_by_name, "PB_1", id="by_name"),
        pytest.param(ProductBlockTable.find_by_tag, "PB1", id="by_tag"),
    ],
)
def test_product_block_finders(finder, key, generic_product_block_1):
    assert finder(key).product_block_id == generic_product_block_1.product_block_id


@pytest.mark.parametrize(
    "finder",
    [
        pytest.param(ProductBlockTable.find_by_name, id="by_name"),
        pytest.param(ProductBlockTable.find_by_tag, id="by_tag"),
    ],
)
def test_product_block_finders_raise_when_missing(finder):
    with pytest.raises(NoResultFound):
        finder("does-not-exist")


def test_find_by_product_tag_is_deprecated_and_matches_select(generic_subscription_1):
    with pytest.warns(DeprecationWarning, match="select_by_product_tag"):
        legacy_ids = [sub.subscription_id for sub in SubscriptionTable.find_by_product_tag("GEN1").all()]

    expected_ids = [sub.subscription_id for sub in db.session.scalars(SubscriptionTable.select_by_product_tag("GEN1"))]
    assert legacy_ids == expected_ids == [UUID(generic_subscription_1)]
