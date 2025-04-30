from http import HTTPStatus
from uuid import uuid4

import pytest
from sqlalchemy import delete

from orchestrator.db import WorkflowTable, db

WORKFLOW_ID = uuid4()


@pytest.fixture
def seed():
    db.session.execute(delete(WorkflowTable))
    workflow = WorkflowTable(
        name="workflow123",
        target="CREATE",
        description="Original description of the workflow",
        workflow_id=WORKFLOW_ID,
    )
    db.session.add(workflow)
    db.session.commit()


def test_workflow_by_id_404(seed, test_client):
    response = test_client.get(f"/api/workflows/{str(uuid4())}")
    assert HTTPStatus.NOT_FOUND == response.status_code


def test_update_description(seed, test_client):
    body = {
        "description": "BLABLA",
    }
    response = test_client.patch(f"/api/workflows/{WORKFLOW_ID}", json=body)

    assert response.json()["description"] == "BLABLA"


def test_update_description_with_empty_body(seed, test_client):
    get_before = test_client.get(f"/api/workflows/{WORKFLOW_ID}")
    body = {}
    response = test_client.patch(f"/api/workflows/{WORKFLOW_ID}", json=body)

    assert HTTPStatus.CREATED == response.status_code
    get_after = test_client.get(f"/api/workflows/{WORKFLOW_ID}")

    assert get_before.json()["description"] == get_after.json()["description"]


def test_update_description_nonexistent_workflow(seed, test_client):
    random_uuid = uuid4()
    body = {
        "description": "BLABLA",
    }
    response = test_client.patch(f"/api/workflows/{random_uuid}", json=body)

    assert HTTPStatus.NOT_FOUND == response.status_code
