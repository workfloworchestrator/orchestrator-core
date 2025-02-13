from http import HTTPStatus
from uuid import uuid4

import pytest
from sqlalchemy import delete

from orchestrator.db import ResourceTypeTable, db

RESOURCE_TYPE_ID = uuid4()


@pytest.fixture
def seed():
    db.session.execute(delete(ResourceTypeTable))
    resource_type = ResourceTypeTable(
        resource_type="Resource type 123",
        description="Original description of the resource type",
        resource_type_id=RESOURCE_TYPE_ID,
    )
    db.session.add(resource_type)
    db.session.commit()


def test_resource_type_by_id_404(seed, test_client):
    response = test_client.get(f"/api/resource_types/{str(uuid4())}")
    assert HTTPStatus.NOT_FOUND == response.status_code


def test_update_description(seed, test_client):
    body = {
        "description": "BLABLA",
    }
    response = test_client.patch(f"/api/resource_types/{RESOURCE_TYPE_ID}", json=body)

    assert response.json()["description"] == "BLABLA"


def test_update_description_with_empty_body(seed, test_client):
    get_before = test_client.get(f"/api/resource_types/{RESOURCE_TYPE_ID}")
    body = {}
    response = test_client.patch(f"/api/resource_types/{RESOURCE_TYPE_ID}", json=body)

    assert HTTPStatus.CREATED == response.status_code
    get_after = test_client.get(f"/api/resource_types/{RESOURCE_TYPE_ID}")

    assert get_before.json()["description"] == get_after.json()["description"]


def test_update_description_nonexistent_resource_type(seed, test_client):
    random_uuid = uuid4()
    body = {
        "description": "BLABLA",
    }
    response = test_client.patch(f"/api/resource_types/{random_uuid}", json=body)

    assert HTTPStatus.NOT_FOUND == response.status_code
