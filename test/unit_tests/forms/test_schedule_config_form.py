from http import HTTPStatus

from inline_snapshot import snapshot


def test_forms_endpoint_scheduler_config_without_initial_form_input(test_client):
    user_input = [
        {"task": "Validate subscriptions", "schedule_type": "Once"},
        {
            "task": "Validate subscriptions",
            "schedule_type": "Once",
        },
    ]
    response = test_client.post("/api/forms/configure_schedule", json=user_input)

    assert response.status_code == HTTPStatus.CREATED
    response_data = response.json()
    assert response_data == snapshot(
        {
            "workflow_id": response_data["workflow_id"],
            "task": "Validate subscriptions",
            "schedule_type": "Once",
            "start_date": response_data["start_date"],
            "workflow_name": "task_validate_subscriptions",
            "trigger": "Once",
            "trigger_kwargs": {},
            "user_inputs": [],
        }
    )


def test_forms_endpoint_scheduler_config_with_initial_form_input(test_client, generic_subscription_1):
    user_input = [
        {"task": "Validate all subscriptions of Product Type", "schedule_type": "Once"},
        {
            "task": "Validate all subscriptions of Product Type",
            "schedule_type": "Once",
        },
        {"product_type": "Generic"},
    ]
    response = test_client.post("/api/forms/configure_schedule", json=user_input)

    assert response.status_code == HTTPStatus.CREATED
    response_data = response.json()
    assert response_data == snapshot(
        {
            "workflow_id": response_data["workflow_id"],
            "task": "Validate all subscriptions of Product Type",
            "schedule_type": "Once",
            "start_date": response_data["start_date"],
            "workflow_name": "task_validate_product_type",
            "trigger": "Once",
            "trigger_kwargs": {},
            "user_inputs": [{"product_type": "Generic"}],
        }
    )


def test_forms_endpoint_scheduler_config_interval_type(test_client):
    user_input = [
        {"task": "Validate subscriptions", "schedule_type": "Interval"},
        {
            "task": "Validate subscriptions",
            "schedule_type": "Interval",
            "interval": "1 hour",
        },
    ]
    response = test_client.post("/api/forms/configure_schedule", json=user_input)

    assert response.status_code == HTTPStatus.CREATED
    response_data = response.json()
    assert response_data == snapshot(
        {
            "workflow_id": response_data["workflow_id"],
            "task": "Validate subscriptions",
            "schedule_type": "Interval",
            "interval": "1 hour",
            "start_date": response_data["start_date"],
            "workflow_name": "task_validate_subscriptions",
            "trigger": "Interval",
            "trigger_kwargs": {"hours": 1},
            "user_inputs": [],
        }
    )


def test_forms_endpoint_scheduler_config_cron_type(test_client):
    user_input = [
        {"task": "Validate subscriptions", "schedule_type": "Cron"},
        {
            "task": "Validate subscriptions",
            "schedule_type": "Cron",
            "cron": "0 9 * * 1-5",
        },
    ]
    response = test_client.post("/api/forms/configure_schedule", json=user_input)

    assert response.status_code == HTTPStatus.CREATED
    response_data = response.json()
    assert response_data == snapshot(
        {
            "workflow_id": response_data["workflow_id"],
            "task": "Validate subscriptions",
            "schedule_type": "Cron",
            "cron": "0 9 * * 1-5",
            "start_date": response_data["start_date"],
            "workflow_name": "task_validate_subscriptions",
            "trigger": "Cron",
            "trigger_kwargs": {"cron": "0 9 * * 1-5"},
            "user_inputs": [],
        }
    )
