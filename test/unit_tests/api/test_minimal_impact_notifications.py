from http import HTTPStatus
from uuid import uuid4

import pytest

from orchestrator.db import MinimalImpactNotificationTable, ProductTable, SubscriptionTable, db
from orchestrator.db.models import ImpactNotificationLevel

SUBSCRIPTION_ID = uuid4()
SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID = uuid4()
CUSTOMER_ID = uuid4()


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
        customer_id=uuid4(),
        minimal_impact_notifications=[
            MinimalImpactNotificationTable(
                id=SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID,
                customer_id=CUSTOMER_ID,
                impact=ImpactNotificationLevel.LOSS_OF_RESILIENCY,
            )
        ],
    )

    db.session.add(product)
    db.session.add(subscription)
    db.session.commit()


def test_get_by_id(seed, test_client):
    response = test_client.get(f"/api/minimal_impact_notifications/{SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID}")
    assert HTTPStatus.OK == response.status_code


def test_get_404(seed, test_client):
    random_uuid = uuid4()
    response = test_client.get(f"/api/minimal_impact_notifications/{random_uuid}")
    assert HTTPStatus.NOT_FOUND == response.status_code


def test_get_by_customer_and_subscription_id(seed, test_client):
    url = f"/api/minimal_impact_notifications/customer/{CUSTOMER_ID}/subscription/{SUBSCRIPTION_ID}"
    response = test_client.get(url)
    assert HTTPStatus.OK == response.status_code
    assert response.json()["id"] == str(SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID)


def test_get_by_customer(seed, test_client):
    url = f"/api/minimal_impact_notifications/customer/{CUSTOMER_ID}/"
    response = test_client.get(url)
    assert HTTPStatus.OK == response.status_code
    assert response.json()[0]["id"] == str(SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID)


def test_save(seed, test_client):
    body = {
        "subscription_id": SUBSCRIPTION_ID,
        "customer_id": uuid4(),
        "impact": ImpactNotificationLevel.NEVER,
    }
    response = test_client.post("/api/minimal_impact_notifications/", json=body)
    assert HTTPStatus.NO_CONTENT == response.status_code

    count = db.session.query(MinimalImpactNotificationTable).count()
    assert 2 == count


def test_update(seed, test_client):
    new_impact_level = ImpactNotificationLevel.DOWN_TIME
    body = {
        "id": SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID,
        "subscription_id": SUBSCRIPTION_ID,
        "customer_id": uuid4(),
        "impact": new_impact_level,
    }
    response = test_client.put("/api/minimal_impact_notifications/", json=body)
    assert HTTPStatus.NO_CONTENT == response.status_code

    count = db.session.query(MinimalImpactNotificationTable).count()
    assert 1 == count

    res = db.session.query(MinimalImpactNotificationTable).first()
    assert new_impact_level == res.impact


def test_delete(seed, test_client):
    test_client.delete(f"/api/minimal_impact_notifications/{SUBSCRIPTION_CUSTOMER_DESCRIPTION_ID}")

    count = db.session.query(MinimalImpactNotificationTable).count()
    assert 0 == count
