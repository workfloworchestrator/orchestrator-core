from http import HTTPStatus

from orchestrator.db import WorkflowTable
from orchestrator.targets import Target

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
