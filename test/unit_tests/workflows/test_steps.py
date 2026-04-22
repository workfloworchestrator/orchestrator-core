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

"""Tests for workflow steps: unsync (fallback/backup/insync logic), store_process_subscription deprecation, and refresh_search_index error handling."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from orchestrator.core.domain.base import SubscriptionModel
from orchestrator.core.workflows.steps import (
    refresh_process_search_index,
    refresh_subscription_search_index,
    store_process_subscription,
    unsync,
)


@pytest.fixture
def subscription_id():
    return str(uuid4())


@pytest.fixture
def mock_subscription_model():
    sub = MagicMock(spec=SubscriptionModel)
    sub.insync = True
    sub.subscription_id = uuid4()
    sub.model_dump.return_value = {"field": "value"}
    return sub


@pytest.fixture
def validation_error():
    return ValidationError.from_exception_data(title="test", line_errors=[], input_type="python")


def _make_state(subscription_id, old_subscriptions=None):
    state = {"subscription_id": subscription_id}
    if old_subscriptions is not None:
        state["__old_subscriptions__"] = old_subscriptions
    return state


# --- unsync ---


@patch("orchestrator.core.workflows.steps.sync_invalidate_subscription_cache")
@patch("orchestrator.core.workflows.steps.get_subscription")
@patch("orchestrator.core.workflows.steps.SubscriptionModel.from_subscription")
def test_unsync_validation_error_fallback(
    mock_from_sub, mock_get_sub, mock_invalidate, subscription_id, validation_error
):
    """When SubscriptionModel.from_subscription raises ValidationError, fall back to get_subscription."""
    mock_from_sub.side_effect = validation_error
    fallback_sub = MagicMock()
    fallback_sub.insync = True
    fallback_sub.subscription_id = subscription_id
    mock_get_sub.return_value = fallback_sub

    result = unsync(_make_state(subscription_id))

    assert result.issuccess()
    state = result.unwrap()
    mock_get_sub.assert_called_once_with(subscription_id)
    assert state["subscription"] == fallback_sub
    assert fallback_sub.insync is False


@patch("orchestrator.core.workflows.steps.sync_invalidate_subscription_cache")
@patch("orchestrator.core.workflows.steps.SubscriptionModel.from_subscription")
def test_unsync_existing_backup_skips(mock_from_sub, mock_invalidate, subscription_id, mock_subscription_model):
    """When __old_subscriptions__ already has the subscription_id key, don't overwrite."""
    mock_from_sub.return_value = mock_subscription_model
    existing_backup = {subscription_id: {"old": "data"}}

    result = unsync(_make_state(subscription_id, existing_backup))

    assert result.issuccess()
    state = result.unwrap()
    assert state["__old_subscriptions__"][subscription_id] == {"old": "data"}


@patch("orchestrator.core.workflows.steps.sync_invalidate_subscription_cache")
@patch("orchestrator.core.workflows.steps.SubscriptionModel.from_subscription")
def test_unsync_already_out_of_sync_fails(mock_from_sub, mock_invalidate, subscription_id):
    """Subscription with insync=False raises ValueError, wrapped as Failed by step decorator."""
    sub = MagicMock()
    sub.insync = False
    mock_from_sub.return_value = sub

    result = unsync(_make_state(subscription_id))

    assert result.isfailed()


@patch("orchestrator.core.workflows.steps.sync_invalidate_subscription_cache")
@patch("orchestrator.core.workflows.steps.SubscriptionModel.from_subscription")
def test_unsync_creates_backup_for_model(mock_from_sub, mock_invalidate, subscription_id, mock_subscription_model):
    """Normal path: creates backup using model_dump for SubscriptionModel."""
    mock_from_sub.return_value = mock_subscription_model

    result = unsync(_make_state(subscription_id))

    assert result.issuccess()
    state = result.unwrap()
    assert str(subscription_id) in state["__old_subscriptions__"]
    assert state["__old_subscriptions__"][str(subscription_id)] == {"field": "value"}
    assert mock_subscription_model.insync is False


# --- store_process_subscription ---


def test_store_process_subscription_deprecation_warning():
    from orchestrator.core.targets import Target

    with patch("orchestrator.core.workflows.steps.logger") as mock_logger:
        store_process_subscription(Target.CREATE)
        mock_logger.warning.assert_called_once()
        assert "deprecated" in mock_logger.warning.call_args[0][0].lower()


# --- refresh_search_index ---


@pytest.mark.parametrize(
    "step_fn,state_key,state_value",
    [
        pytest.param(refresh_subscription_search_index, "subscription", MagicMock(), id="subscription"),
        pytest.param(refresh_process_search_index, "process_id", str(uuid4()), id="process"),
    ],
)
@patch("orchestrator.core.workflows.steps.reset_search_index")
def test_refresh_search_index_exception_swallowed(mock_reset, step_fn, state_key, state_value):
    mock_reset.side_effect = RuntimeError("search error")
    result = step_fn({state_key: state_value})
    assert result.issuccess()
