# Copyright 2019-2026 SURF, ESnet, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from http import HTTPStatus
from uuid import uuid4

import pytest
from sqlalchemy import delete

from orchestrator.core.db import (
    FixedInputTable,
    ProductBlockTable,
    ProductTable,
    ResourceTypeTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    SubscriptionTable,
    db,
)
from test.integration_tests.config import (
    CITY_TYPE,
    DOMAIN,
    IMS_CIRCUIT_ID,
    PORT_SPEED,
    PORT_SUBSCRIPTION_ID,
    SERVICE_SPEED,
)
from test.integration_tests.fixtures.workflows import add_soft_deleted_workflows  # noqa: F401

PRODUCT_ID = uuid4()
MSP_PRODUCT_ID = uuid4()
UNPROTECTED_MSP_SSP_ID = uuid4()
PROTECTED_MSP_SSP_ID = uuid4()
REDUNDANT_MSP_SSP_ID = uuid4()
SUBSCRIPTION_ID = uuid4()
depends_on_SUBSCRIPTION_ID = uuid4()


@pytest.fixture(autouse=True)
def _add_soft_deleted_workflows(add_soft_deleted_workflows):  # noqa: F811
    add_soft_deleted_workflows(10)


@pytest.fixture
def seed():
    db.session.execute(delete(ProductTable))
    resources = [
        ResourceTypeTable(resource_type=IMS_CIRCUIT_ID, description="IMS circuit Id"),
    ]
    product_blocks = [ProductBlockTable(name="Ethernet", description="d", status="active", resource_types=resources)]
    fixed_inputs = [
        FixedInputTable(name=SERVICE_SPEED, value="1000"),
        FixedInputTable(name=CITY_TYPE, value="inner_city"),
        FixedInputTable(name="protection_type", value="Protected"),
    ]
    product = ProductTable(
        product_id=PRODUCT_ID,
        name="LightPath",
        description="descr",
        product_type="LightPath",
        tag="LightPath",
        status="active",
        product_blocks=product_blocks,
        fixed_inputs=fixed_inputs,
    )
    msp_product = ProductTable(
        product_id=MSP_PRODUCT_ID,
        name="MSP",
        description="descr",
        product_type="Port",
        tag="Port",
        status="active",
        product_blocks=product_blocks,
        fixed_inputs=[FixedInputTable(name=PORT_SPEED, value="1000"), FixedInputTable(name=DOMAIN, value="SURFNET7")],
    )
    msp_product_100G = ProductTable(
        name="MSP 1100G",
        description="descr",
        product_type="Port",
        tag="Port",
        status="active",
        product_blocks=product_blocks,
        fixed_inputs=[
            FixedInputTable(name=PORT_SPEED, value="100000"),
            FixedInputTable(name="domain", value="SURFNET7"),
        ],
    )
    product_no_workflow = ProductTable(
        product_id=uuid4(), name="P", description="P", product_type="Port", tag="P", status="active"
    )

    port_subscription_id = ResourceTypeTable(resource_type=PORT_SUBSCRIPTION_ID, description="Port Subscription Id")
    values = [SubscriptionInstanceValueTable(resource_type=port_subscription_id, value=str(depends_on_SUBSCRIPTION_ID))]
    subscription = SubscriptionTable(
        subscription_id=SUBSCRIPTION_ID,
        description="desc",
        status="active",
        insync=True,
        product=product,
        customer_id=str(uuid4()),
        instances=[SubscriptionInstanceTable(product_block=product_blocks[0], values=values)],
    )
    depends_on_subscription = SubscriptionTable(
        subscription_id=depends_on_SUBSCRIPTION_ID,
        description="desc",
        status="active",
        insync=True,
        product=msp_product,
        customer_id=str(uuid4()),
    )

    def lp_product(protection_type, product_id, speed="1000"):
        name = f"msp_ssp_{protection_type.lower()}"
        msp_ssp_fixed_inputs = [
            FixedInputTable(name="protection_type", value=protection_type.capitalize()),
            FixedInputTable(name=SERVICE_SPEED, value=speed),
            FixedInputTable(name=CITY_TYPE, value="inner_city"),
        ]
        return ProductTable(
            product_id=product_id,
            name=f"name_{product_id}",
            description=name,
            product_type="LightPath",
            tag="LightPath",
            status="active",
            fixed_inputs=msp_ssp_fixed_inputs,
        )

    db.session.add(product)
    db.session.add(msp_product)
    db.session.add(msp_product_100G)
    db.session.add(lp_product("protected", uuid4(), speed="10000"))
    db.session.add(lp_product("protected", uuid4(), speed="750"))
    db.session.add(lp_product("redundant", REDUNDANT_MSP_SSP_ID))
    db.session.add(lp_product("protected", PROTECTED_MSP_SSP_ID, speed="250"))
    db.session.add(lp_product("unprotected", UNPROTECTED_MSP_SSP_ID))
    db.session.add(subscription)
    db.session.add(depends_on_subscription)
    db.session.add(product_no_workflow)
    db.session.commit()


def test_fetch_all_products(seed, test_client):
    response = test_client.get("/api/products")

    assert HTTPStatus.OK == response.status_code
    products = response.json()

    assert 9 == len(products)


def test_fetch_all_products_by_tag_and_port(seed, test_client):
    response = test_client.get("/api/products?tag=LightPath&product_type=LightPath")

    assert HTTPStatus.OK == response.status_code
    products = response.json()

    assert 6 == len(products)


def test_fetch_all_products_by_unknown_tag(seed, test_client):
    response = test_client.get("/api/products?tag=Nope")

    assert HTTPStatus.OK == response.status_code
    products = response.json()

    assert 0 == len(products)


def test_product_by_id(seed, test_client):
    response = test_client.get(f"/api/products/{PRODUCT_ID}")

    assert HTTPStatus.OK == response.status_code
    product = response.json()
    expected_value = [fi for fi in product["fixed_inputs"] if fi["name"] == SERVICE_SPEED][0]["value"]
    assert "1000" == expected_value
    assert "Ethernet" == product["product_blocks"][0]["name"]


def test_product_by_id_404(seed, test_client):
    response = test_client.get(f"/api/products/{str(uuid4())}")
    assert HTTPStatus.NOT_FOUND == response.status_code


def test_update_description(seed, test_client):
    body = {
        "description": "BLABLA",
    }
    response = test_client.patch(f"/api/products/{PRODUCT_ID}", json=body)

    assert response.json()["description"] == "BLABLA"


def test_update_description_with_empty_body(seed, test_client):
    get_before = test_client.get(f"/api/products/{PRODUCT_ID}")
    body = {}
    response = test_client.patch(f"/api/products/{PRODUCT_ID}", json=body)

    assert HTTPStatus.CREATED == response.status_code
    get_after = test_client.get(f"/api/products/{PRODUCT_ID}")

    assert get_before.json()["description"] == get_after.json()["description"]


def test_update_description_nonexistent_product(seed, test_client):
    random_uuid = uuid4()
    body = {
        "description": "BLABLA",
    }
    response = test_client.patch(f"/api/products/{random_uuid}", json=body)

    assert HTTPStatus.NOT_FOUND == response.status_code


def test_fetch_products_by_product_type_only(seed, test_client):
    response = test_client.get("/api/products?product_type=Port")

    assert HTTPStatus.OK == response.status_code
    products = response.json()

    assert 3 == len(products)
    assert all(p["product_type"] == "Port" for p in products)


def test_product_by_id_returns_correct_data(seed, test_client):
    response = test_client.get(f"/api/products/{PRODUCT_ID}")

    assert HTTPStatus.OK == response.status_code
    product = response.json()

    assert product["name"] == "LightPath"


def test_update_status(seed, test_client):
    """Patching status to a non-EOL value should succeed."""
    body = {"status": "phase out"}
    response = test_client.patch(f"/api/products/{PRODUCT_ID}", json=body)

    assert HTTPStatus.CREATED == response.status_code
    assert response.json()["status"] == "phase out"


def test_update_status_end_of_life_with_active_subscriptions(seed, test_client):
    """Cannot set 'end of life' when product has non-terminated subscriptions."""
    body = {"status": "end of life"}
    response = test_client.patch(f"/api/products/{PRODUCT_ID}", json=body)

    assert HTTPStatus.BAD_REQUEST == response.status_code
    assert "not in terminated state" in response.json()["detail"]


def test_update_status_end_of_life_with_terminated_subscriptions(seed, test_client):
    """Can set 'end of life' when all subscriptions are terminated."""
    subscription = db.session.get(SubscriptionTable, SUBSCRIPTION_ID)
    subscription.status = "terminated"
    db.session.commit()

    body = {"status": "end of life"}
    response = test_client.patch(f"/api/products/{PRODUCT_ID}", json=body)

    assert HTTPStatus.CREATED == response.status_code
    assert response.json()["status"] == "end of life"


def test_update_status_invalid_value(seed, test_client):
    """Invalid status value should return 422 Unprocessable Entity."""
    body = {"status": "invalid_status"}
    response = test_client.patch(f"/api/products/{PRODUCT_ID}", json=body)

    assert HTTPStatus.UNPROCESSABLE_ENTITY == response.status_code


def test_update_description_and_status(seed, test_client):
    """Patching both description and status should update both."""
    body = {"description": "Updated", "status": "pre production"}
    response = test_client.patch(f"/api/products/{PRODUCT_ID}", json=body)

    assert HTTPStatus.CREATED == response.status_code
    assert response.json()["description"] == "Updated"
    assert response.json()["status"] == "pre production"
