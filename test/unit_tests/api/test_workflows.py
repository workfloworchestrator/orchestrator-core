from http import HTTPStatus
from os import getenv

import pytest
from redis import Redis

from orchestrator.db import WorkflowTable
from orchestrator.domain.base import SubscriptionModel
from orchestrator.settings import app_settings
from orchestrator.targets import Target
from orchestrator.utils.functional import orig
from orchestrator.workflows.steps import cache_domain_models

PRODUCT_ID = "fb28e465-87fd-4d23-9c75-ed036529e416"


def test_workflows(test_client):
    response = test_client.get("/api/workflows")

    assert HTTPStatus.OK == response.status_code
    workflows = response.json()

    assert len(workflows) == WorkflowTable.query.count()
    for workflow in workflows:
        assert workflow["name"] is not None
        assert workflow["target"] is not None


def test_workflows_by_target(test_client):
    for target, num_wfs in [
        (Target.CREATE, WorkflowTable.query.filter(WorkflowTable.target == Target.CREATE).count()),
        (Target.TERMINATE, WorkflowTable.query.filter(WorkflowTable.target == Target.TERMINATE).count()),
        (Target.MODIFY, WorkflowTable.query.filter(WorkflowTable.target == Target.MODIFY).count()),
    ]:
        response = test_client.get(f"/api/workflows?target={target}")
        workflows = response.json()
        assert len(workflows) == num_wfs
        for wf in workflows:
            assert target == wf["target"]


def test_get_all_with_product_tags(test_client):
    response = test_client.get("/api/workflows/with_product_tags")

    assert HTTPStatus.OK == response.status_code
    assert len(response.json()) == WorkflowTable.query.count()


@pytest.mark.skipif(
    not getenv("AIOCACHE_DISABLE", "0") == "0", reason="AIOCACHE must be enabled for this test to do anything"
)
def test_push_subscriptions_to_cache_step(generic_subscription_1):
    push_subscription = orig(cache_domain_models)
    push_subscription("Aribtrary_name", SubscriptionModel.from_subscription(generic_subscription_1))

    cache = Redis(host=app_settings.CACHE_HOST, port=app_settings.CACHE_PORT)
    assert cache.get(f"domain:{generic_subscription_1}") is None

    app_settings.CACHE_DOMAIN_MODELS = True
    push_subscription("Aribtrary_name", SubscriptionModel.from_subscription(generic_subscription_1))
    result = cache.get(f"domain:{generic_subscription_1}")
    assert result is not None
    app_settings.CACHE_DOMAIN_MODELS = False
