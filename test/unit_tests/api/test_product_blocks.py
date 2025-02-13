from http import HTTPStatus
from uuid import uuid4

import pytest
from sqlalchemy import delete

from orchestrator.db import ProductBlockTable, db

PRODUCT_BLOCK_ID = uuid4()


@pytest.fixture
def seed():
    db.session.execute(delete(ProductBlockTable))
    product_block = ProductBlockTable(
        product_block_id=PRODUCT_BLOCK_ID,
        name="Product block 123",
        description="Original description of the product block",
        tag="tag123",
        status="active",
    )
    db.session.add(product_block)
    db.session.commit()


def test_product_block_by_id_404(seed, test_client):
    response = test_client.get(f"/api/product_blocks/{str(uuid4())}")
    assert HTTPStatus.NOT_FOUND == response.status_code


def test_update_description(seed, test_client):
    body = {
        "description": "BLABLA",
    }
    response = test_client.patch(f"/api/product_blocks/{PRODUCT_BLOCK_ID}", json=body)

    assert response.json()["description"] == "BLABLA"


def test_update_description_with_empty_body(seed, test_client):
    get_before = test_client.get(f"/api/product_blocks/{PRODUCT_BLOCK_ID}")
    body = {}
    response = test_client.patch(f"/api/product_blocks/{PRODUCT_BLOCK_ID}", json=body)

    assert HTTPStatus.CREATED == response.status_code
    get_after = test_client.get(f"/api/product_blocks/{PRODUCT_BLOCK_ID}")

    assert get_before.json()["description"] == get_after.json()["description"]


def test_update_description_nonexistent_product_block(seed, test_client):
    random_uuid = uuid4()
    body = {
        "description": "BLABLA",
    }
    response = test_client.patch(f"/api/product_blocks/{random_uuid}", json=body)

    assert HTTPStatus.NOT_FOUND == response.status_code
