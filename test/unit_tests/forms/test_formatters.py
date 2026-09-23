# Copyright 2026 SURF, GÉANT.
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

"""Tests for the built-in summary field formatters."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from orchestrator.core.forms.summary_form import formatters as f
from orchestrator.core.forms.summary_form.formatters import subscription_summary_fields

# --- subscription_summary_fields ---


@pytest.fixture
def mock_subscription():
    sub = MagicMock()
    sub.subscription_id = uuid4()
    sub.description = "some description"
    sub._product_block_fields_ = {"ip_block": None}
    return sub


def test_subscription_summary_fields_includes_block_title(mock_subscription):
    mock_subscription.ip_block.title = "Block title"

    with patch.object(f, "SubscriptionModel") as mock_model:
        mock_model.from_subscription.return_value = mock_subscription

        result = list(subscription_summary_fields(mock_subscription.subscription_id))

    assert result == [
        ("subscription_id", str(mock_subscription.subscription_id)),
        ("description", "some description"),
        ("title", "Block title"),
    ]


def test_subscription_summary_fields_defaults_title_when_block_has_none(mock_subscription):
    del mock_subscription.ip_block.title

    with patch.object(f, "SubscriptionModel") as mock_model:
        mock_model.from_subscription.return_value = mock_subscription

        result = list(subscription_summary_fields(mock_subscription.subscription_id))

    assert result[-1] == ("title", "-")
