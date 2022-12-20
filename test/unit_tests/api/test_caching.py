"""(regression)tests in relation to domain model caching."""
from http import HTTPStatus
from os import getenv
from unittest.mock import patch

import pytest
from nwastdlib.url import URL
from redis import Redis

from orchestrator.domain.base import SubscriptionModel
from orchestrator.services.subscriptions import build_extended_domain_model
from orchestrator.settings import app_settings
from orchestrator.utils.redis import to_redis


@pytest.fixture
def cache_fixture():
    # Fixture to enable domain model caching and cleanup keys added to the list
    with patch.object(app_settings, "CACHE_DOMAIN_MODELS", True):
        cache = Redis(host=app_settings.CACHE_HOST, port=app_settings.CACHE_PORT)
        to_cleanup = []

        yield to_cleanup

        for key in to_cleanup:
            try:
                cache.delete(key)
            except Exception as exc:
                print("failed to delete cache key", key, str(exc))  # noqa: T001, T201


@pytest.mark.skipif(
    not getenv("AIOCACHE_DISABLE", "0") == "0", reason="AIOCACHE must be enabled for this test to do anything"
)
def test_cache_update_customer_description(
    test_client, generic_subscription_1, make_customer_description, cache_fixture
):
    """Check that updating subscription customer description is reflected in the cache."""
    subscription = SubscriptionModel.from_subscription(generic_subscription_1)
    cust_desc = make_customer_description(
        subscription_id=subscription.subscription_id,
        customer_id=subscription.customer_id,
        description="Original description",
    )
    extended_model = build_extended_domain_model(subscription)

    # Add domainmodel to cache
    to_redis(extended_model)
    cache_fixture.extend([f"domain:{generic_subscription_1}", f"domain:etag:{generic_subscription_1}"])

    # Retrieve domain-model, customer description should be as inserted
    response1 = test_client.get(URL("api/subscriptions/domain-model") / generic_subscription_1)
    assert response1.json()["customer_descriptions"][0]["description"] == "Original description"

    # Update customer description
    body = {
        "id": cust_desc.id,
        "subscription_id": subscription.subscription_id,
        "customer_id": subscription.customer_id,
        "description": "Updated description",
    }
    response2 = test_client.put("/api/subscription_customer_descriptions/", json=body)
    assert HTTPStatus.NO_CONTENT == response2.status_code

    # Check that description is updated in the domain-model
    response2 = test_client.get(URL("api/subscriptions/domain-model") / generic_subscription_1)
    assert response2.json()["customer_descriptions"][0]["description"] == "Updated description"


@pytest.mark.skipif(
    not getenv("AIOCACHE_DISABLE", "0") == "0", reason="AIOCACHE must be enabled for this test to do anything"
)
def test_cache_delete_customer_description(
    test_client, generic_subscription_1, make_customer_description, cache_fixture
):
    """Check that deleting subscription customer description is reflected in the cache."""
    subscription = SubscriptionModel.from_subscription(generic_subscription_1)
    cust_desc = make_customer_description(
        subscription_id=subscription.subscription_id,
        customer_id=subscription.customer_id,
        description="Original description",
    )
    extended_model = build_extended_domain_model(subscription)

    # Add domainmodel to cache
    to_redis(extended_model)
    cache_fixture.extend([f"domain:{generic_subscription_1}", f"domain:etag:{generic_subscription_1}"])

    # Retrieve domain-model, customer description should be as inserted
    response1 = test_client.get(URL("api/subscriptions/domain-model") / generic_subscription_1)
    assert response1.json()["customer_descriptions"][0]["description"] == "Original description"

    # Delete customer description
    response2 = test_client.delete(f"/api/subscription_customer_descriptions/{cust_desc.id}")
    assert HTTPStatus.NO_CONTENT == response2.status_code

    # Check that description is removed from the domain-model
    response2 = test_client.get(URL("api/subscriptions/domain-model") / generic_subscription_1)
    assert response2.json()["customer_descriptions"] == []


@pytest.mark.skipif(
    not getenv("AIOCACHE_DISABLE", "0") == "0", reason="AIOCACHE must be enabled for this test to do anything"
)
def test_cache_create_customer_description(
    test_client, generic_subscription_1, make_customer_description, cache_fixture
):
    """Check that creating subscription customer description is reflected in the cache."""
    subscription = SubscriptionModel.from_subscription(generic_subscription_1)
    extended_model = build_extended_domain_model(subscription)

    # Add domainmodel to cache
    to_redis(extended_model)
    cache_fixture.extend([f"domain:{generic_subscription_1}", f"domain:etag:{generic_subscription_1}"])

    # Retrieve domain-model, customer description should be empty
    response1 = test_client.get(URL("api/subscriptions/domain-model") / generic_subscription_1)
    assert response1.json()["customer_descriptions"] == []

    # Create customer description
    body = {
        "subscription_id": subscription.subscription_id,
        "customer_id": subscription.customer_id,
        "description": "New description",
    }
    response2 = test_client.post("/api/subscription_customer_descriptions/", json=body)
    assert HTTPStatus.NO_CONTENT == response2.status_code

    # Check that description is updated in the domain-model
    response2 = test_client.get(URL("api/subscriptions/domain-model") / generic_subscription_1)
    assert len(response2.json()["customer_descriptions"]) > 0
    assert response2.json()["customer_descriptions"][0]["description"] == "New description"
