from http import HTTPStatus
from uuid import uuid4

import pytest

from orchestrator.db import ProductTable, SubscriptionCustomerDescriptionTable, SubscriptionTable, db

SUBSCRIPTION_ID = uuid4()
SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID = uuid4()
CUSTOMER_ID = str(uuid4())


@pytest.fixture
def seed():
    product = ProductTable(
        name="ProductTable", description="description", product_type="Port", tag="Port", status="active"
    )
    subscription = SubscriptionTable(
        subscription_id=SUBSCRIPTION_ID,
        description="desc",
        status="active",
        insync=True,
        product=product,
        customer_id=str(uuid4()),
        customer_descriptions=[
            SubscriptionCustomerDescriptionTable(
                id=SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID, customer_id=CUSTOMER_ID, description="customer other alias"
            )
        ],
        version=1,
    )

    db.session.add(product)
    db.session.add(subscription)
    db.session.commit()


def test_get_by_id(seed, test_client):
    response = test_client.get(f"/api/subscription_customer_descriptions/{SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID}")
    assert HTTPStatus.OK == response.status_code


def test_get_404(seed, test_client):
    random_uuid = uuid4()
    response = test_client.get(f"/api/subscription_customer_descriptions/{random_uuid}")
    assert HTTPStatus.NOT_FOUND == response.status_code


def test_get_by_customer_and_subscription_id(seed, test_client):
    url = f"/api/subscription_customer_descriptions/customer/{CUSTOMER_ID}/subscription/{SUBSCRIPTION_ID}"
    response = test_client.get(url)
    assert HTTPStatus.OK == response.status_code
    assert response.json()["id"] == str(SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID)


def test_save(seed, test_client):
    body = {
        "subscription_id": SUBSCRIPTION_ID,
        "customer_id": str(uuid4()),
        "description": "Customer specific alias",
    }
    response = test_client.post("/api/subscription_customer_descriptions/", json=body)
    assert HTTPStatus.NO_CONTENT == response.status_code

    count = db.session.query(SubscriptionCustomerDescriptionTable).count()
    assert 2 == count


def test_update(seed, test_client):
    new_desc = "Updated specific alias"
    body = {
        "id": SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID,
        "subscription_id": SUBSCRIPTION_ID,
        "customer_id": CUSTOMER_ID,
        "description": new_desc,
    }
    response = test_client.put("/api/subscription_customer_descriptions/", json=body)
    assert HTTPStatus.NO_CONTENT == response.status_code

    count = db.session.query(SubscriptionCustomerDescriptionTable).count()
    assert 1 == count

    customer_description = db.session.query(SubscriptionCustomerDescriptionTable).first()
    assert new_desc == customer_description.description
    assert 2 == customer_description.version


def test_update_with_version(seed, test_client):
    new_desc = "Updated specific alias"
    version = 1
    body = {
        "id": SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID,
        "subscription_id": SUBSCRIPTION_ID,
        "customer_id": CUSTOMER_ID,
        "description": new_desc,
        "version": version,
    }
    response = test_client.put("/api/subscription_customer_descriptions/", json=body)
    assert HTTPStatus.NO_CONTENT == response.status_code

    count = db.session.query(SubscriptionCustomerDescriptionTable).count()
    assert 1 == count

    customer_description = db.session.query(SubscriptionCustomerDescriptionTable).first()
    assert new_desc == customer_description.description
    assert version + 1 == customer_description.version


def test_update_with_lower_version_invalid(seed, test_client):
    new_desc = "Updated specific alias"
    body = {
        "id": SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID,
        "subscription_id": SUBSCRIPTION_ID,
        "customer_id": CUSTOMER_ID,
        "description": new_desc,
        "version": 0,
    }
    response = test_client.put("/api/subscription_customer_descriptions/", json=body)
    assert HTTPStatus.BAD_REQUEST == response.status_code

    data = response.json()
    assert "Stale data: given version (0) does not match the current version (1)" == data["detail"]


def test_update_with_higher_version_invalid(seed, test_client):
    new_desc = "Updated specific alias"
    body = {
        "id": SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID,
        "subscription_id": SUBSCRIPTION_ID,
        "customer_id": CUSTOMER_ID,
        "description": new_desc,
        "version": 10,
    }
    response = test_client.put("/api/subscription_customer_descriptions/", json=body)
    assert HTTPStatus.BAD_REQUEST == response.status_code

    data = response.json()
    assert "Stale data: given version (10) does not match the current version (1)" == data["detail"]


def test_delete(seed, test_client):
    test_client.delete(f"/api/subscription_customer_descriptions/{SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID}")

    count = db.session.query(SubscriptionCustomerDescriptionTable).count()
    assert 0 == count
