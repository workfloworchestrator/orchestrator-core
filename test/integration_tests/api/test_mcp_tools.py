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

from http import HTTPStatus


def test_list_subscriptions(product_type_1_subscription_factory, product_type_1_subscriptions_factory, test_client):
    older_id, newer_id = product_type_1_subscriptions_factory(2)
    initial_id = product_type_1_subscription_factory(description="not yet provisioned", start_date=None)

    response = test_client.post("/api/agent/list_subscriptions", json={})

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["has_more"] is False
    # Newest first; a NULL start_date means not yet provisioned, i.e. newest.
    assert [s["subscription_id"] for s in body["subscriptions"]] == [initial_id, newer_id, older_id]


def test_list_subscriptions_truncates_at_limit(product_type_1_subscriptions_factory, test_client):
    product_type_1_subscriptions_factory(2)

    response = test_client.post("/api/agent/list_subscriptions", json={"limit": 1})

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert len(body["subscriptions"]) == 1
    assert body["has_more"] is True
