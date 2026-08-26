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

"""Tests for the process-exit indexing hook: state extraction, entity indexing and strictness."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from orchestrator.core.search.indexing.hooks import extract_subscription_ids

pytestmark = pytest.mark.search

SUB_ID_A = str(uuid4())
SUB_ID_B = str(uuid4())


@pytest.mark.parametrize(
    "state,expected",
    [
        pytest.param({}, set(), id="empty-state"),
        pytest.param({"unrelated": "value"}, set(), id="no-subscription-keys"),
        pytest.param({"subscription_id": SUB_ID_A}, {SUB_ID_A}, id="subscription-id-str"),
        pytest.param({"subscription_id": None}, set(), id="subscription-id-none"),
        pytest.param({"subscription": {"subscription_id": SUB_ID_A}}, {SUB_ID_A}, id="subscription-serialized-dict"),
        pytest.param(
            {"subscription": SimpleNamespace(subscription_id=SUB_ID_A)}, {SUB_ID_A}, id="subscription-model-like"
        ),
        pytest.param({"subscriptions": [SUB_ID_A, SUB_ID_B]}, {SUB_ID_A, SUB_ID_B}, id="subscriptions-list-of-str"),
        pytest.param(
            {"subscriptions": [{"subscription_id": SUB_ID_A}, SimpleNamespace(subscription_id=SUB_ID_B)]},
            {SUB_ID_A, SUB_ID_B},
            id="subscriptions-list-mixed",
        ),
        pytest.param({"subscription_ids": (SUB_ID_A, SUB_ID_B)}, {SUB_ID_A, SUB_ID_B}, id="subscription-ids-tuple"),
        pytest.param(
            {"subscription": SimpleNamespace(subscription_id=SUB_ID_A), "subscription_id": SUB_ID_A},
            {SUB_ID_A},
            id="duplicates-deduped",
        ),
        pytest.param({"subscription": "not-a-uuid-but-a-string"}, {"not-a-uuid-but-a-string"}, id="opaque-string"),
        pytest.param({"subscription": 42}, set(), id="unsupported-type-ignored"),
        pytest.param("not-a-dict", set(), id="state-not-a-dict"),
        pytest.param(None, set(), id="state-none"),
    ],
)
def test_extract_subscription_ids(state, expected):
    assert extract_subscription_ids(state) == expected


def test_extract_subscription_ids_accepts_uuid_objects():
    subscription_id = uuid4()
    assert extract_subscription_ids({"subscription_id": subscription_id}) == {str(subscription_id)}
