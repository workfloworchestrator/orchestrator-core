from http import HTTPStatus
from uuid import uuid4

import pytest

from orchestrator.db import ProductBlockTable, ResourceTypeTable, db

RESOURCE_TYPE_ID = "f51f9542-e83f-42e5-a590-0284dd5493e4"


@pytest.fixture
def seed():
    # Delete current resource types
    ResourceTypeTable.query.delete()
    resource_types = [ResourceTypeTable(resource_type_id=RESOURCE_TYPE_ID, resource_type="some_resource_type")]
    product_block = ProductBlockTable(
        name="Ethernet", description="desc", status="active", resource_types=resource_types
    )
    db.session.add(product_block)
    db.session.commit()


def test_fetch_all_resource_types(seed, test_client):
    response = test_client.get("/api/resource_types")

    assert HTTPStatus.OK == response.status_code
    resource_types = response.json()

    assert 1 == len(resource_types)


def test_save_resource_type(seed, test_client):
    body = {"resource_type": "some"}
    response = test_client.post("/api/resource_types/", json=body)

    assert HTTPStatus.NO_CONTENT == response.status_code
    assert 2 == len(test_client.get("/api/resource_types").json())


def test_save_invalid_resource_type(seed, test_client):
    response = test_client.post("/api/resource_types/", json={})

    assert HTTPStatus.UNPROCESSABLE_ENTITY == response.status_code
    assert {
        "detail": [{"loc": ["body", "resource_type"], "msg": "field required", "type": "value_error.missing"}]
    } == response.json()


def test_update_resource_type(seed, test_client):
    body = {"resource_type_id": RESOURCE_TYPE_ID, "resource_type": "changed"}
    response = test_client.put("/api/resource_types/", json=body)

    assert HTTPStatus.NO_CONTENT == response.status_code
    resource_type = test_client.get(f"/api/resource_types/{RESOURCE_TYPE_ID}").json()

    assert "changed" == resource_type["resource_type"]


def test_delete_resource_type(seed, test_client):
    rt_id = uuid4()
    body = {"resource_type_id": rt_id, "resource_type": "some"}
    test_client.post("/api/resource_types/", json=body)
    response = test_client.delete(f"/api/resource_types/{rt_id}")
    assert HTTPStatus.NO_CONTENT == response.status_code


def test_delete_product_block_with_used_products(seed, test_client):
    response = test_client.delete(f"/api/resource_types/{RESOURCE_TYPE_ID}")
    assert HTTPStatus.BAD_REQUEST == response.status_code

    assert f"ResourceType {RESOURCE_TYPE_ID} is used in ProductBlocks: Ethernet" == response.json()["detail"]
