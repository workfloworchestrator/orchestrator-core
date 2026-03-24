from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from orchestrator.domain.base import SubscriptionModel
from orchestrator.workflows.steps import (
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


class TestUnsync:
    @patch("orchestrator.workflows.steps.sync_invalidate_subscription_cache")
    @patch("orchestrator.workflows.steps.get_subscription")
    @patch("orchestrator.workflows.steps.SubscriptionModel.from_subscription")
    def test_validation_error_fallback(
        self, mock_from_sub, mock_get_sub, mock_invalidate, subscription_id, validation_error
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

    @patch("orchestrator.workflows.steps.sync_invalidate_subscription_cache")
    @patch("orchestrator.workflows.steps.SubscriptionModel.from_subscription")
    def test_existing_backup_skips(self, mock_from_sub, mock_invalidate, subscription_id, mock_subscription_model):
        """When __old_subscriptions__ already has the subscription_id key, don't overwrite."""
        mock_from_sub.return_value = mock_subscription_model
        existing_backup = {subscription_id: {"old": "data"}}

        result = unsync(_make_state(subscription_id, existing_backup))

        assert result.issuccess()
        state = result.unwrap()
        assert state["__old_subscriptions__"][subscription_id] == {"old": "data"}

    @patch("orchestrator.workflows.steps.sync_invalidate_subscription_cache")
    @patch("orchestrator.workflows.steps.to_serializable")
    @patch("orchestrator.workflows.steps.get_subscription")
    @patch("orchestrator.workflows.steps.SubscriptionModel.from_subscription")
    def test_non_model_serialization(
        self, mock_from_sub, mock_get_sub, mock_to_serial, mock_invalidate, subscription_id, validation_error
    ):
        """When fallback returns a non-SubscriptionModel, use to_serializable."""
        mock_from_sub.side_effect = validation_error
        fallback_sub = MagicMock(spec=[])  # not isinstance SubscriptionModel
        fallback_sub.insync = True
        fallback_sub.subscription_id = subscription_id
        mock_get_sub.return_value = fallback_sub
        mock_to_serial.return_value = {"serialized": "data"}

        result = unsync(_make_state(subscription_id))

        assert result.issuccess()
        state = result.unwrap()
        mock_to_serial.assert_called_once_with(fallback_sub)
        assert state["__old_subscriptions__"][str(subscription_id)] == {"serialized": "data"}

    @patch("orchestrator.workflows.steps.sync_invalidate_subscription_cache")
    @patch("orchestrator.workflows.steps.SubscriptionModel.from_subscription")
    def test_already_out_of_sync_raises(self, mock_from_sub, mock_invalidate, subscription_id):
        """Subscription with insync=False raises ValueError, wrapped as Failed by step decorator."""
        sub = MagicMock()
        sub.insync = False
        mock_from_sub.return_value = sub

        result = unsync(_make_state(subscription_id))

        assert result.isfailed()

    @patch("orchestrator.workflows.steps.sync_invalidate_subscription_cache")
    @patch("orchestrator.workflows.steps.SubscriptionModel.from_subscription")
    def test_creates_backup_for_model(self, mock_from_sub, mock_invalidate, subscription_id, mock_subscription_model):
        """Normal path: creates backup using model_dump for SubscriptionModel."""
        mock_from_sub.return_value = mock_subscription_model

        result = unsync(_make_state(subscription_id))

        assert result.issuccess()
        state = result.unwrap()
        assert str(subscription_id) in state["__old_subscriptions__"]
        assert state["__old_subscriptions__"][str(subscription_id)] == {"field": "value"}
        assert mock_subscription_model.insync is False


class TestStoreProcessSubscription:
    def test_deprecation_warning(self):
        """Providing a workflow target logs a deprecation warning."""
        from orchestrator.targets import Target

        with patch("orchestrator.workflows.steps.logger") as mock_logger:
            store_process_subscription(Target.CREATE)
            mock_logger.warning.assert_called_once()
            assert "deprecated" in mock_logger.warning.call_args[0][0].lower()

    def test_no_warning_without_target(self):
        """No deprecation warning when no target provided."""
        with patch("orchestrator.workflows.steps.logger") as mock_logger:
            store_process_subscription()
            mock_logger.warning.assert_not_called()


@pytest.mark.parametrize(
    "step_fn,state_key,state_value",
    [
        (refresh_subscription_search_index, "subscription", MagicMock()),
        (refresh_process_search_index, "process_id", str(uuid4())),
    ],
)
class TestRefreshSearchIndex:
    @patch("orchestrator.workflows.steps.llm_settings")
    @patch("orchestrator.workflows.steps.reset_search_index")
    def test_search_enabled_calls_indexing(self, mock_reset, mock_llm, step_fn, state_key, state_value):
        mock_llm.SEARCH_ENABLED = True

        with patch.dict(
            "sys.modules",
            {
                "orchestrator.search.core.types": MagicMock(),
                "orchestrator.search.indexing": MagicMock(),
            },
        ):
            result = step_fn({state_key: state_value})

        mock_reset.assert_called_once()
        assert result.issuccess()

    @patch("orchestrator.workflows.steps.llm_settings")
    @patch("orchestrator.workflows.steps.reset_search_index")
    def test_search_disabled_skips_indexing(self, mock_reset, mock_llm, step_fn, state_key, state_value):
        mock_llm.SEARCH_ENABLED = False

        result = step_fn({state_key: state_value})

        mock_reset.assert_called_once()
        assert result.issuccess()

    @patch("orchestrator.workflows.steps.reset_search_index")
    def test_exception_swallowed(self, mock_reset, step_fn, state_key, state_value):
        mock_reset.side_effect = RuntimeError("search error")

        result = step_fn({state_key: state_value})

        assert result.issuccess()

    @patch("orchestrator.workflows.steps.llm_settings")
    @patch("orchestrator.workflows.steps.reset_search_index")
    def test_no_entity(self, mock_reset, mock_llm, step_fn, state_key, state_value):
        mock_llm.SEARCH_ENABLED = True

        result = step_fn({state_key: None})

        mock_reset.assert_called_once()
        assert result.issuccess()
