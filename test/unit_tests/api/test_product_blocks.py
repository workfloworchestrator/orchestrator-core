from http import HTTPStatus
from uuid import uuid4

import pytest

from orchestrator.db import ProductBlockTable, ProductTable, ResourceTypeTable, db
from test.unit_tests.config import IMS_CIRCUIT_ID

PRODUCT_BLOCK_ID = "f51f9542-e83f-42e5-a590-0284dd5493e4"


@pytest.fixture
def seed():
    ProductBlockTable.query.delete()
    resources = [ResourceTypeTable(resource_type=IMS_CIRCUIT_ID, description="IMS Circuit Id")]
    product_blocks = [
        ProductBlockTable(
            product_block_id=PRODUCT_BLOCK_ID,
            name="Ethernet",
            description="desc",
            status="active",
            resource_types=resources,
            tag="tag",
        )
    ]
    product = ProductTable(
        name="ProductTable",
        description="description",
        product_type="Port",
        tag="Port",
        status="active",
        product_blocks=product_blocks,
        fixed_inputs=[],
    )

    db.session.add(product)
    db.session.commit()


def test_fetch_all_product_blocks(seed, test_client):
    response = test_client.get("/api/product_blocks")

    assert HTTPStatus.OK == response.status_code
    product_blocks = response.json()

    assert 1 == len(product_blocks)


def test_get_by_id(seed, test_client):
    product_block = test_client.get(f"/api/product_blocks/{PRODUCT_BLOCK_ID}").json()
    assert IMS_CIRCUIT_ID == product_block["resource_types"][0]["resource_type"]


def test_save_product_block(seed, test_client):
    body = {"name": "Circuit", "description": "desc", "status": "active"}
    response = test_client.post("/api/product_blocks/", json=body)
    assert HTTPStatus.NO_CONTENT == response.status_code
    assert 2 == len(test_client.get("/api/product_blocks").json())


def test_save_product_block_with_existing_resource_type(seed, test_client):
    resource_type = test_client.get("/api/resource_types").json()[0]
    body = {"name": "Circuit", "description": "desc", "status": "active", "resource_types": [resource_type]}
    response = test_client.post("/api/product_blocks/", json=body)

    assert HTTPStatus.NO_CONTENT == response.status_code
    assert 2 == len(test_client.get("/api/product_blocks").json())


def test_save_invalid_product_block(seed, test_client):
    response = test_client.post("/api/product_blocks/", json=({}))

    assert HTTPStatus.UNPROCESSABLE_ENTITY == response.status_code
    assert {
        "detail": [
            {"loc": ["body", "name"], "msg": "field required", "type": "value_error.missing"},
            {"loc": ["body", "description"], "msg": "field required", "type": "value_error.missing"},
        ]
    } == response.json()


def test_update_product_block(seed, test_client):
    body = {"product_block_id": PRODUCT_BLOCK_ID, "name": "Circuit", "description": "desc", "status": "end of life"}
    response = test_client.put("/api/product_blocks/", json=body)
    assert HTTPStatus.NO_CONTENT == response.status_code
    product_block = test_client.get(f"/api/product_blocks/{PRODUCT_BLOCK_ID}").json()
    assert "end of life" == product_block["status"]


def test_delete_product_block(seed, test_client):
    pb_id = str(uuid4())
    body = {"product_block_id": pb_id, "name": "Circuit", "description": "desc", "status": "active"}
    test_client.post("/api/product_blocks/", json=body)

    response = test_client.delete(f"/api/product_blocks/{pb_id}")
    assert HTTPStatus.NO_CONTENT == response.status_code


def test_delete_product_block_with_used_products(seed, test_client):
    response = test_client.delete(f"/api/product_blocks/{PRODUCT_BLOCK_ID}")
    assert HTTPStatus.BAD_REQUEST == response.status_code

    assert f"ProductBlock {PRODUCT_BLOCK_ID} is used in Products: ProductTable" == response.json()["detail"]
