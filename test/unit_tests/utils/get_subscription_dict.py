from os import getenv
from unittest import mock
from unittest.mock import Mock

import pytest

from orchestrator import app_settings
from orchestrator.domain.base import SubscriptionModel
from orchestrator.services.subscriptions import build_extended_domain_model
from orchestrator.utils.get_subscription_dict import get_subscription_dict
from orchestrator.utils.redis import to_redis


@mock.patch.object(app_settings, "CACHE_DOMAIN_MODELS", False)
@mock.patch("orchestrator.utils.get_subscription_dict._generate_etag")
async def test_get_subscription_dict_db(generate_etag, generic_subscription_1):
    generate_etag.side_effect = Mock(return_value="etag-mock")
    await get_subscription_dict(generic_subscription_1)
    assert generate_etag.called


@pytest.mark.skipif(
    not getenv("AIOCACHE_DISABLE", "0") == "0", reason="AIOCACHE must be enabled for this test to do anything"
)
@mock.patch("orchestrator.utils.get_subscription_dict._generate_etag")
async def test_get_subscription_dict_cache(generate_etag, generic_subscription_1, cache_fixture):
    subscription = SubscriptionModel.from_subscription(generic_subscription_1)
    extended_model = build_extended_domain_model(subscription)

    # Add domainmodel to cache
    to_redis(extended_model)
    cache_fixture.extend([f"domain:{generic_subscription_1}", f"domain:etag:{generic_subscription_1}"])

    generate_etag.side_effect = Mock(return_value="etag-mock")
    await get_subscription_dict(generic_subscription_1)
    assert not generate_etag.called
