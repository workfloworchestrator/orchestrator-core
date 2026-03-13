from http import HTTPStatus

from inline_snapshot import snapshot

from orchestrator.schemas.schedules import APSchedulerJobCreate


def test_forms_endpoint_scheduler_config_without_initial_form_input(test_client):
    user_input = [
        {"task": "Validate subscriptions"},
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
            "scheduled_type": "create",
            "name": None,
            "workflow_id": response_data["workflow_id"],
            "workflow_name": "task_validate_subscriptions",
            "trigger": "date",
            "trigger_kwargs": {"run_date": response_data["trigger_kwargs"]["run_date"]},
            "user_inputs": [],
        }
    )
    assert APSchedulerJobCreate(**response_data)


def test_forms_endpoint_scheduler_config_with_initial_form_input(test_client, generic_subscription_1):
    user_input = [
        {"task": "Validate all subscriptions of Product Type"},
        {"product_type": "Generic"},
        {"task": "Validate all subscriptions of Product Type", "schedule_type": "Once"},
        {
            "task": "Validate all subscriptions of Product Type",
            "schedule_type": "Once",
        },
    ]
    response = test_client.post("/api/forms/configure_schedule", json=user_input)

    assert response.status_code == HTTPStatus.CREATED
    response_data = response.json()
    assert response_data == snapshot(
        {
            "workflow_id": response_data["workflow_id"],
            "workflow_name": "task_validate_product_type",
            "trigger": "date",
            "trigger_kwargs": {"run_date": response_data["trigger_kwargs"]["run_date"]},
            "user_inputs": [{"product_type": "Generic"}],
            "scheduled_type": "create",
            "name": None,
        }
    )
    assert APSchedulerJobCreate(**response_data)


def test_forms_endpoint_scheduler_config_interval_type(test_client):
    user_input = [
        {"task": "Validate subscriptions"},
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
            "scheduled_type": "create",
            "name": None,
            "workflow_id": response_data["workflow_id"],
            "workflow_name": "task_validate_subscriptions",
            "trigger": "interval",
            "trigger_kwargs": {"start_date": response_data["trigger_kwargs"]["start_date"], "hours": 1},
            "user_inputs": [],
        }
    )
    assert APSchedulerJobCreate(**response_data)


def test_forms_endpoint_scheduler_config_cron_type(test_client):
    user_input = [
        {"task": "Validate subscriptions"},
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
            "scheduled_type": "create",
            "name": None,
            "workflow_id": response_data["workflow_id"],
            "workflow_name": "task_validate_subscriptions",
            "trigger": "cron",
            "trigger_kwargs": {
                "start_date": response_data["trigger_kwargs"]["start_date"],
                "minute": 0,
                "hour": 9,
                "day": None,
                "month": None,
                "day_of_week": None,
            },
            "user_inputs": [],
        }
    )
    assert APSchedulerJobCreate(**response_data)
