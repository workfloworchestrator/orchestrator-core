from http import HTTPStatus
from uuid import uuid4

import pytest

from orchestrator.db import FixedInputTable, ProductTable, SubscriptionTable, db

PRODUCT_ID = str(uuid4())
SUBSCRIPTION_ID = str(uuid4())
PORT_SPEED_VALUE = "100000"
SERVICE_SPEED_VALUE = "100000"
PORT_SPEED = "port_speed"
SERVICE_SPEED = "service_speed"


@pytest.fixture
def seed():
    FixedInputTable.query.delete()
    fixed_inputs = [
        FixedInputTable(name=PORT_SPEED, value=PORT_SPEED_VALUE),
        FixedInputTable(name=SERVICE_SPEED, value=SERVICE_SPEED_VALUE),
    ]
    product = ProductTable(
        product_id=PRODUCT_ID,
        name="ProductTable",
        description="description",
        product_type="Port",
        tag="SSP",
        status="active",
        fixed_inputs=fixed_inputs,
    )
    subscription = SubscriptionTable(
        subscription_id=SUBSCRIPTION_ID,
        description="desc",
        status="active",
        insync=True,
        product=product,
        customer_id=uuid4(),
    )

    db.session.add(product)
    db.session.add(subscription)
    db.session.commit()


def test_configuration(seed, test_client):
    response = test_client.get("/api/fixed_inputs/configuration")
    assert HTTPStatus.OK == response.status_code
    config = response.json()
    fixed_inputs_config = list(map(lambda x: x["name"], config["fixed_inputs"]))
    for tag, fixed_inputs in config["by_tag"].items():
        for fi in fixed_inputs:
            name = list(fi.keys())[0]
            assert name in fixed_inputs_config, f"{tag} has non-existent fixed_input: {name}"
