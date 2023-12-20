from http import HTTPStatus
from os import getenv

import pytest
from redis import Redis
from sqlalchemy import func, select

from orchestrator.db import WorkflowTable, db
from orchestrator.domain.base import SubscriptionModel
from orchestrator.services.workflows import get_workflows
from orchestrator.settings import app_settings
from orchestrator.targets import Target
from orchestrator.utils.functional import orig
from orchestrator.workflows.steps import cache_domain_models
from test.unit_tests.fixtures.workflows import add_soft_deleted_workflows  # noqa: F401

PRODUCT_ID = "fb28e465-87fd-4d23-9c75-ed036529e416"


@pytest.fixture(autouse=True)
def _add_soft_deleted_workflows(add_soft_deleted_workflows):  # noqa: F811
    add_soft_deleted_workflows(10)


def test_workflows(test_client):
    response = test_client.get("/api/workflows")

    assert response.status_code == HTTPStatus.OK
    workflows = response.json()

    assert len(workflows) == len(list(get_workflows()))
    assert all(workflow["name"] is not None for workflow in workflows)
    assert all(workflow["target"] is not None for workflow in workflows)


def test_deleted_workflows_are_filtered(test_client):
    all_workflows = get_workflows(include_deleted=True)
    response = test_client.get("/api/workflows")

    assert response.status_code == HTTPStatus.OK
    workflows = response.json()
    assert len(workflows) == len(list(all_workflows)) - 10


@pytest.mark.parametrize("target", (Target.CREATE, Target.TERMINATE, Target.MODIFY))
def test_workflows_by_target(target, test_client):
    response = test_client.get(f"/api/workflows?target={target}")
    workflows = response.json()

    num_wfs = db.session.scalar(select(func.count(WorkflowTable.workflow_id)).where(WorkflowTable.target == target))
    assert len(workflows) == num_wfs
    assert all(target == workflow["target"] for workflow in workflows)


@pytest.mark.parametrize(
    "include_steps, predicate",
    ((False, lambda workflow: workflow["steps"] is None), (True, lambda workflow: len(workflow["steps"]) > 0)),
)
def test_workflows_include_steps(include_steps, predicate, test_client):
    response = test_client.get(f"/api/workflows?include_steps={include_steps}")

    assert response.status_code == HTTPStatus.OK
    workflows = response.json()

    assert len(workflows) == len(list(get_workflows()))
    assert all(predicate(workflow) for workflow in workflows)


def test_get_all_with_product_tags(test_client):
    response = test_client.get("/api/workflows/with_product_tags")

    assert response.status_code == HTTPStatus.OK
    num_wfs = len(db.session.scalars(WorkflowTable.select()).all())
    assert len(response.json()) == num_wfs


@pytest.mark.skipif(
    not getenv("AIOCACHE_DISABLE", "0") == "0", reason="AIOCACHE must be enabled for this test to do anything"
)
def test_push_subscriptions_to_cache_step(generic_subscription_1):
    push_subscription = orig(cache_domain_models)
    push_subscription("Aribtrary_name", SubscriptionModel.from_subscription(generic_subscription_1))

    cache = Redis.from_url(str(app_settings.CACHE_URI))
    assert cache.get(f"domain:{generic_subscription_1}") is None

    app_settings.CACHE_DOMAIN_MODELS = True
    push_subscription("Aribtrary_name", SubscriptionModel.from_subscription(generic_subscription_1))
    result = cache.get(f"domain:{generic_subscription_1}")
    assert result is not None
    app_settings.CACHE_DOMAIN_MODELS = False
