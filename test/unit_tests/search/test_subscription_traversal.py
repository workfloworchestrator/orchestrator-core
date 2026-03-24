"""Tests for SubscriptionTraverser: end-to-end model traversal for simple, nested, and computed property subscriptions."""

# Copyright 2019-2025 SURF, GÉANT.
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

from orchestrator.search.core.types import EntityType
from orchestrator.search.indexing.registry import ENTITY_CONFIG_REGISTRY
from orchestrator.search.indexing.traverse import SubscriptionTraverser


def _assert_traverse_fields_match(mock_load_model, mock_db_subscription, subscription_instance, expected_fields):
    mock_load_model.return_value = subscription_instance
    config = ENTITY_CONFIG_REGISTRY[EntityType.SUBSCRIPTION]

    model = SubscriptionTraverser._load_model(sub=mock_db_subscription)
    extracted_fields = list(SubscriptionTraverser.traverse(model, path=config.root_name))

    expected_set = set(expected_fields)
    actual_set = set(extracted_fields)

    missing_fields = expected_set - actual_set
    extra_fields = actual_set - expected_set

    assert not missing_fields, f"Missing fields: {missing_fields}"
    assert not extra_fields, f"Extra fields: {extra_fields}"
    assert len(extracted_fields) == len(expected_fields)


@pytest.mark.parametrize(
    "instance_fixture,fields_fixture",
    [
        pytest.param("subscription_instance", "expected_traverse_fields", id="real-subscription"),
        pytest.param("simple_subscription_instance", "simple_expected_fields", id="simple-direct-block"),
        pytest.param("nested_subscription_instance", "nested_expected_fields", id="nested-blocks"),
        pytest.param(
            "computed_property_subscription_instance", "computed_property_expected_fields", id="computed-property"
        ),
    ],
)
def test_traverse_subscription(request, mock_load_model, mock_db_subscription, instance_fixture, fields_fixture):
    subscription_instance = request.getfixturevalue(instance_fixture)
    expected_fields = request.getfixturevalue(fields_fixture)
    _assert_traverse_fields_match(mock_load_model, mock_db_subscription, subscription_instance, expected_fields)
