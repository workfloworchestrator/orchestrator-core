from orchestrator.db import db
from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle
from test.unit_tests.conftest import CUSTOMER_ID


def test_subscription_metrics_active_subscription(test_client, product_type_1_subscriptions_factory) -> None:
    product_type_1_subscriptions_factory()
    expected_metric = (
        f'wfo_subscriptions_count{{customer_id="{CUSTOMER_ID}",insync="True",lifecycle_state="active",'
        f'product_name="Product 1"}} 1.0'
    )
    response = test_client.get("/api/metrics")
    assert expected_metric in response.text

    product_type_1_subscriptions_factory(4)

    expected_metric = (
        f'wfo_subscriptions_count{{customer_id="{CUSTOMER_ID}",insync="True",lifecycle_state="active",'
        f'product_name="Product 1"}} 5.0'  # We now expect 5 subscriptions of the same type.
    )
    response = test_client.get("/api/metrics")
    assert expected_metric in response.text


def test_subscription_metrics_subscription_lifecycles(test_client, generic_subscription_1) -> None:
    subscription = SubscriptionModel.from_subscription(generic_subscription_1)
    for lifecycle_state in SubscriptionLifecycle.values():
        subscription = SubscriptionModel.from_other_lifecycle(subscription, lifecycle_state)
        subscription.save()
        db.session.commit()
        expected_metric = (
            f'wfo_subscriptions_count{{customer_id="{CUSTOMER_ID}",insync="True",lifecycle_state="{lifecycle_state}",'
            f'product_name="Product 1"}} 1.0'
        )
        response = test_client.get("/api/metrics")
        assert expected_metric in response.text


def test_subscription_metrics_subscription_sync(test_client, generic_subscription_1) -> None:
    subscription = SubscriptionModel.from_subscription(generic_subscription_1)
    subscription.insync = False
    subscription.save()
    db.session.commit()
    expected_metric = (
        f'wfo_subscriptions_count{{customer_id="{CUSTOMER_ID}",insync="False",lifecycle_state="active",'
        f'product_name="Product 1"}} 1.0'
    )
    response = test_client.get("/api/metrics")
    assert expected_metric in response.text

    subscription.insync = True
    subscription.save()
    db.session.commit()
    expected_metric = (
        f'wfo_subscriptions_count{{customer_id="{CUSTOMER_ID}",insync="True",lifecycle_state="active",'
        f'product_name="Product 1"}} 1.0'
    )
    response = test_client.get("/api/metrics")
    assert expected_metric in response.text
