from unittest.mock import MagicMock, patch

from orchestrator.workflows.tasks.validate_subscriptions import validate_subscriptions

PATCH_PREFIX = "orchestrator.workflows.tasks.validate_subscriptions"


@patch(f"{PATCH_PREFIX}.start_validation_workflow_for_workflows")
@patch(f"{PATCH_PREFIX}.get_validation_product_workflows_for_subscription")
@patch(f"{PATCH_PREFIX}.get_subscriptions_on_product_table_in_sync")
@patch(f"{PATCH_PREFIX}.app_settings")
def test_in_sync_path(mock_settings, mock_get_subs, mock_get_workflows, mock_start):
    """VALIDATE_OUT_OF_SYNC_SUBSCRIPTIONS=False uses in_sync query and starts validation workflows."""
    mock_settings.VALIDATE_OUT_OF_SYNC_SUBSCRIPTIONS = False
    sub1 = MagicMock()
    sub1.product.name = "Product1"
    mock_get_subs.return_value = [sub1]
    mock_get_workflows.return_value = ["wf1"]

    result = validate_subscriptions({})

    assert result.issuccess()
    mock_get_subs.assert_called_once()
    mock_get_workflows.assert_called_once_with(sub1)
    mock_start.assert_called_once_with(subscription=sub1, workflows=["wf1"])


@patch(f"{PATCH_PREFIX}.start_validation_workflow_for_workflows")
@patch(f"{PATCH_PREFIX}.get_validation_product_workflows_for_subscription")
@patch(f"{PATCH_PREFIX}.get_subscriptions_on_product_table")
@patch(f"{PATCH_PREFIX}.app_settings")
def test_out_of_sync_path(mock_settings, mock_get_subs, mock_get_workflows, mock_start):
    """VALIDATE_OUT_OF_SYNC_SUBSCRIPTIONS=True uses all subscriptions query."""
    mock_settings.VALIDATE_OUT_OF_SYNC_SUBSCRIPTIONS = True
    sub1 = MagicMock()
    sub1.product.name = "Product1"
    mock_get_subs.return_value = [sub1]
    mock_get_workflows.return_value = ["wf1"]

    result = validate_subscriptions({})

    assert result.issuccess()
    mock_get_subs.assert_called_once()
    mock_start.assert_called_once()


@patch(f"{PATCH_PREFIX}.start_validation_workflow_for_workflows")
@patch(f"{PATCH_PREFIX}.get_validation_product_workflows_for_subscription")
@patch(f"{PATCH_PREFIX}.get_subscriptions_on_product_table_in_sync")
@patch(f"{PATCH_PREFIX}.app_settings")
def test_no_validation_workflow_breaks(mock_settings, mock_get_subs, mock_get_workflows, mock_start):
    """When no validation workflows found, log warning and break."""
    mock_settings.VALIDATE_OUT_OF_SYNC_SUBSCRIPTIONS = False
    sub1 = MagicMock()
    sub1.product.name = "Product1"
    sub2 = MagicMock()
    sub2.product.name = "Product2"
    mock_get_subs.return_value = [sub1, sub2]
    mock_get_workflows.return_value = []

    result = validate_subscriptions({})

    assert result.issuccess()
    mock_get_workflows.assert_called_once_with(sub1)
    mock_start.assert_not_called()


@patch(f"{PATCH_PREFIX}.start_validation_workflow_for_workflows")
@patch(f"{PATCH_PREFIX}.get_validation_product_workflows_for_subscription")
@patch(f"{PATCH_PREFIX}.get_subscriptions_on_product_table_in_sync")
@patch(f"{PATCH_PREFIX}.app_settings")
def test_empty_subscriptions(mock_settings, mock_get_subs, mock_get_workflows, mock_start):
    """Empty subscription list means nothing happens."""
    mock_settings.VALIDATE_OUT_OF_SYNC_SUBSCRIPTIONS = False
    mock_get_subs.return_value = []

    result = validate_subscriptions({})

    assert result.issuccess()
    mock_get_workflows.assert_not_called()
    mock_start.assert_not_called()
