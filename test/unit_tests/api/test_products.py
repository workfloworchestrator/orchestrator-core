from http import HTTPStatus
from uuid import uuid4

import pytest

from orchestrator.db import (
    FixedInputTable,
    ProductBlockTable,
    ProductTable,
    ResourceTypeTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    SubscriptionTable,
    db,
)
from test.unit_tests.config import CITY_TYPE, DOMAIN, IMS_CIRCUIT_ID, PORT_SPEED, PORT_SUBSCRIPTION_ID, SERVICE_SPEED

PRODUCT_ID = uuid4()
MSP_PRODUCT_ID = uuid4()
UNPROTECTED_MSP_SSP_ID = uuid4()
PROTECTED_MSP_SSP_ID = uuid4()
REDUNDANT_MSP_SSP_ID = uuid4()
SUBSCRIPTION_ID = uuid4()
CHILD_SUBSCRIPTION_ID = uuid4()


@pytest.fixture
def seed():
    ProductTable.query.delete()
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
    values = [SubscriptionInstanceValueTable(resource_type=port_subscription_id, value=str(CHILD_SUBSCRIPTION_ID))]
    subscription = SubscriptionTable(
        subscription_id=SUBSCRIPTION_ID,
        description="desc",
        status="active",
        insync=True,
        product=product,
        customer_id=uuid4(),
        instances=[SubscriptionInstanceTable(product_block=product_blocks[0], values=values)],
    )
    child_subscription = SubscriptionTable(
        subscription_id=CHILD_SUBSCRIPTION_ID,
        description="desc",
        status="active",
        insync=True,
        product=msp_product,
        customer_id=uuid4(),
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
    db.session.add(child_subscription)
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


def test_save(seed, test_client):
    p_id = uuid4()
    body = {
        "product_id": p_id,
        "name": "MSP_2",
        "description": "MSP",
        "product_type": "Port",
        "tag": "Port",
        "status": "active",
        "fixed_inputs": [{"name": "help", "value": "val"}],
        "product_blocks": [
            {"name": "name", "description": "desc", "status": "active", "resource_types": [{"resource_type": "test"}]}
        ],
    }
    from orchestrator.db import FixedInputTable

    fi = FixedInputTable.query.all()
    response = test_client.post("/api/products/", json=body)
    assert HTTPStatus.NO_CONTENT == response.status_code
    products = test_client.get("/api/products").json()
    assert 10 == len(products)

    fi2 = FixedInputTable.query.all()
    assert len(fi) + 1 == len(fi2)


def test_delete(seed, test_client):
    p_id = uuid4()
    body = {
        "product_id": p_id,
        "name": "DEL",
        "description": "DEL",
        "product_type": "Port",
        "tag": "Port",
        "status": "active",
    }
    test_client.post("/api/products/", json=body)

    response = test_client.delete(f"/api/products/{p_id}")
    assert HTTPStatus.NO_CONTENT == response.status_code


def test_delete_with_subscriptions(seed, test_client):
    response = test_client.delete(f"/api/products/{PRODUCT_ID}")

    assert HTTPStatus.BAD_REQUEST == response.status_code
    assert f"Product {PRODUCT_ID} is used in Subscriptions: desc" == response.json()["detail"]


def test_tags_all(test_client):
    response = test_client.get("/api/products/tags/all")

    assert HTTPStatus.OK == response.status_code
    tags = response.json()

    tags_db = [p.tag for p in ProductTable.query.distinct(ProductTable.tag).all()]
    assert set(tags) == set(tags_db)


def test_types_all(test_client):
    response = test_client.get("/api/products/types/all")

    assert HTTPStatus.OK == response.status_code
    types = response.json()
    types_db = [p.product_type for p in ProductTable.query.distinct(ProductTable.product_type).all()]
    assert set(types) == set(types_db)


def test_statuses_all(seed, test_client):
    response = test_client.get("/api/products/statuses/all")

    assert HTTPStatus.OK == response.status_code
    statuses = response.json()
    assert {"active", "phase out", "pre production", "end of life"}.issubset(set(statuses))
