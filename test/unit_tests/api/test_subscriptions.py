from http import HTTPStatus
from uuid import uuid4

import pytest
from nwastdlib.url import URL

from orchestrator.db import (
    FixedInputTable,
    ProcessSubscriptionTable,
    ProcessTable,
    ProductBlockTable,
    ProductTable,
    ResourceTypeTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    SubscriptionTable,
    db,
)
from orchestrator.services.subscriptions import RELATION_RESOURCE_TYPES, unsync
from orchestrator.workflow import ProcessStatus
from test.unit_tests.config import (
    IMS_CIRCUIT_ID,
    INTERNETPINNEN_PREFIX_SUBSCRIPTION_ID,
    IPAM_PREFIX_ID,
    NODE_SUBSCRIPTION_ID,
    PARENT_IP_PREFIX_SUBSCRIPTION_ID,
    PEER_GROUP_SUBSCRIPTION_ID,
    PORT_SUBSCRIPTION_ID,
)

SERVICE_SUBSCRIPTION_ID = str(uuid4())
PORT_A_SUBSCRIPTION_ID = str(uuid4())
PROVISIONING_PORT_A_SUBSCRIPTION_ID = str(uuid4())
SSP_SUBSCRIPTION_ID = str(uuid4())
IP_PREFIX_SUBSCRIPTION_ID = str(uuid4())
INVALID_SUBSCRIPTION_ID = str(uuid4())
INVALID_PORT_SUBSCRIPTION_ID = str(uuid4())

PRODUCT_ID = str(uuid4())
CUSTOMER_ID = str(uuid4())


@pytest.fixture
def seed():
    # These resource types are special
    resources = [
        ResourceTypeTable(resource_type=IMS_CIRCUIT_ID, description="Desc"),
        ResourceTypeTable(resource_type=PORT_SUBSCRIPTION_ID, description="Desc"),
    ]
    product_blocks = [
        ProductBlockTable(name="ProductBlockA", description="description a", status="active", resource_types=resources)
    ]
    fixed_inputs = [FixedInputTable(name="product_type", value="MSP100G")]
    # Wf needs to exist in code and needs to be a legacy wf with mapping

    lp_product = ProductTable(
        name="LightpathProduct",
        description="Service product that lives on ports",
        product_type="LightPath",
        tag="LightPath",  # This is special since parent/child subscription code handles specific tags
        status="active",
        product_blocks=product_blocks,
        fixed_inputs=fixed_inputs,
    )
    port_a_product = ProductTable(
        product_id=PRODUCT_ID,
        name="PortAProduct",
        description="Port A description",
        product_type="Port",
        tag="SP",  # This is special since parent/child subscription code handles specific tags
        status="active",
        product_blocks=product_blocks,
        fixed_inputs=fixed_inputs,
    )
    port_b_product = ProductTable(
        name="PortBProduct",
        description="Port B description",
        product_type="Port",
        tag="PORTB",
        status="active",
        product_blocks=product_blocks,
        fixed_inputs=fixed_inputs,
    )

    # Special resource type handled by get subscription by ipam prefix endpoint
    ip_prefix_resources = [ResourceTypeTable(resource_type=IPAM_PREFIX_ID, description="Prefix id")]
    ip_prefix_product_blocks = [
        ProductBlockTable(
            name="ProductBlockB", description="description b", status="active", resource_types=ip_prefix_resources
        )
    ]
    ip_prefix_product = ProductTable(
        name="IPPrefixProduct",
        description="ProductTable that is used by service product",
        product_type="IP_PREFIX",
        tag="IP_PREFIX",
        status="active",
        product_blocks=ip_prefix_product_blocks,
    )
    ip_prefix_subscription = SubscriptionTable(
        subscription_id=IP_PREFIX_SUBSCRIPTION_ID,
        description="desc",
        status="active",
        insync=True,
        product=ip_prefix_product,
        customer_id=CUSTOMER_ID,
        instances=[
            SubscriptionInstanceTable(
                product_block=ip_prefix_product_blocks[0],
                values=[SubscriptionInstanceValueTable(resource_type=ip_prefix_resources[0], value="26")],
            )
        ],
    )

    port_a_subscription = SubscriptionTable(
        subscription_id=PORT_A_SUBSCRIPTION_ID,
        description="desc",
        status="initial",
        insync=True,
        product=port_a_product,
        customer_id=CUSTOMER_ID,
        instances=[
            SubscriptionInstanceTable(
                product_block=product_blocks[0],
                values=[SubscriptionInstanceValueTable(resource_type=resources[0], value="54321")],
            )
        ],
    )

    provisioning_port_a_subscription = SubscriptionTable(
        subscription_id=PROVISIONING_PORT_A_SUBSCRIPTION_ID,
        description="desc",
        status="provisioning",
        insync=False,
        product=port_a_product,
        customer_id=CUSTOMER_ID,
        instances=[
            SubscriptionInstanceTable(
                product_block=product_blocks[0],
                values=[SubscriptionInstanceValueTable(resource_type=resources[0], value="12345")],
            )
        ],
    )

    ssp_subscription = SubscriptionTable(
        subscription_id=SSP_SUBSCRIPTION_ID,
        description="desc",
        status="active",
        insync=True,
        product=port_b_product,
        customer_id=CUSTOMER_ID,
        instances=[
            SubscriptionInstanceTable(
                product_block=product_blocks[0],
                values=[SubscriptionInstanceValueTable(resource_type=resources[0], value="54321")],
            )
        ],
    )

    lp_subscription_instance_values_ssp = [
        SubscriptionInstanceValueTable(resource_type=resources[0], value="54321"),
        SubscriptionInstanceValueTable(resource_type=resources[1], value=str(PORT_A_SUBSCRIPTION_ID)),
    ]
    lp_subscription_instance_ssp = SubscriptionInstanceTable(
        product_block=product_blocks[0], values=lp_subscription_instance_values_ssp
    )
    lp_subscription_instance_values_msp = [
        SubscriptionInstanceValueTable(resource_type=resources[0], value="54321"),
        SubscriptionInstanceValueTable(resource_type=resources[1], value=str(SSP_SUBSCRIPTION_ID)),
    ]
    lp_subscription_instance_msp = SubscriptionInstanceTable(
        product_block=product_blocks[0], values=lp_subscription_instance_values_msp
    )
    lp_subscription = SubscriptionTable(
        subscription_id=SERVICE_SUBSCRIPTION_ID,
        description="desc",
        status="active",
        insync=True,
        product=lp_product,
        customer_id=CUSTOMER_ID,
        instances=[lp_subscription_instance_ssp, lp_subscription_instance_msp],
    )

    invalid_subscription = SubscriptionTable(
        subscription_id=INVALID_SUBSCRIPTION_ID,
        description="desc",
        status="active",
        insync=True,
        product=port_a_product,
        customer_id=CUSTOMER_ID,
        instances=[],
    )

    invalid_tagged_product = ProductTable(
        product_id=str(uuid4()),
        name="INVALID_PRODUCT",
        description="invalid descr",
        product_type="Port",
        tag="NEWMSP",
        status="active",
        product_blocks=product_blocks,
        fixed_inputs=fixed_inputs,
    )

    invalid_tagged_subscription = SubscriptionTable(
        subscription_id=INVALID_PORT_SUBSCRIPTION_ID,
        description="desc",
        status="active",
        insync=False,
        product=invalid_tagged_product,
        customer_id=CUSTOMER_ID,
        instances=[
            SubscriptionInstanceTable(
                product_block=product_blocks[0],
                values=[SubscriptionInstanceValueTable(resource_type=resources[0], value="54321")],
            )
        ],
    )
    db.session.add(port_a_product)
    db.session.add(ip_prefix_product)
    db.session.add(ip_prefix_subscription)
    db.session.add(invalid_tagged_product)
    db.session.add(port_b_product)
    db.session.add(lp_product)
    db.session.add(port_a_subscription)
    db.session.add(provisioning_port_a_subscription)
    db.session.add(ssp_subscription)
    db.session.add(lp_subscription)
    db.session.add(invalid_subscription)
    db.session.add(invalid_tagged_subscription)
    db.session.commit()

    RELATION_RESOURCE_TYPES.extend(
        [
            PORT_SUBSCRIPTION_ID,
            IP_PREFIX_SUBSCRIPTION_ID,
            INTERNETPINNEN_PREFIX_SUBSCRIPTION_ID,
            PARENT_IP_PREFIX_SUBSCRIPTION_ID,
            NODE_SUBSCRIPTION_ID,
            PEER_GROUP_SUBSCRIPTION_ID,
        ]
    )

    return ip_prefix_product


def test_subscriptions_all(seed, test_client):
    product_fields = [
        "name",
        "created_at",
        "description",
        "end_date",
        "status",
        "product_type",
        "product_id",
        "tag",
    ]
    subscription_fields = [
        "customer_id",
        "description",
        "status",
        "end_date",
        "insync",
        "start_date",
        "subscription_id",
        "product",
        "name",
        "note",
        "customer_descriptions",
        "product_id",
        "tag",
    ]
    response = test_client.get("/api/subscriptions/all")

    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 7
    for item in response.json():
        # Todo: determine if we want to let the test fail when extra fields are detected?
        product = item["product"]
        # test for extra fields in the response that are not listed in the YAML
        assert set(product.keys()) == set(product_fields)
        assert set(item.keys()) == set(subscription_fields)

        # Check if all listed YAML fields are also available in Response
        for field in product_fields:
            assert field in product
        for field in subscription_fields:
            assert field in item


def test_subscriptions_paginated(seed, test_client):
    product_fields = [
        "name",
        "created_at",
        "description",
        "end_date",
        "status",
        "product_type",
        "product_id",
        "tag",
    ]
    subscription_fields = [
        "customer_id",
        "description",
        "status",
        "end_date",
        "insync",
        "start_date",
        "subscription_id",
        "product",
        "name",
        "note",
        "customer_descriptions",
        "product_id",
        "tag",
    ]
    response = test_client.get("/api/subscriptions")

    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 7

    response = test_client.get("/api/subscriptions/all")

    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 7
    for item in response.json():
        product = item["product"]
        # test for extra fields in the response that are not listed in the YAML
        assert set(product.keys()) == set(product_fields)
        assert set(item.keys()) == set(subscription_fields)

        # Check if all listed YAML fields are also available in Response
        for field in product_fields:
            assert field in product
        for field in subscription_fields:
            assert field in item


def test_filtering_subscriptions(seed, test_client):
    response = test_client.get("/api/subscriptions?filter=status,active")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 5

    response = test_client.get("/api/subscriptions?filter=insync,no")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 2

    response = test_client.get("/api/subscriptions?filter=insync,Y")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 5

    response = test_client.get("/api/subscriptions?filter=insync,no,status,provisioning")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 1

    response = test_client.get("/api/subscriptions?filter=status_gt,active")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 2

    response = test_client.get("/api/subscriptions?filter=status_gte,active")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 7

    response = test_client.get("/api/subscriptions?filter=status_lt,initial")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 5

    response = test_client.get("/api/subscriptions?filter=status_lte,initial")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 6

    response = test_client.get("/api/subscriptions?filter=status,active,product,LightPathProduct")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 1

    response = test_client.get("/api/subscriptions?filter=status,active,product,LightPathProduct-PortBProduct")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 2


def test_sorting_subscriptions(seed, test_client):
    response = test_client.get("/api/subscriptions?sort=status,asc")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 7
    assert response.json()[0]["status"] == "active"
    assert response.json()[6]["status"] == "provisioning"

    response = test_client.get("/api/subscriptions?sort=status,desc")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 7
    assert response.json()[0]["status"] == "provisioning"
    assert response.json()[6]["status"] == "active"

    response = test_client.get("/api/subscriptions?sort=tag,asc")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 7
    assert response.json()[0]["product"]["tag"] == "IP_PREFIX"
    assert response.json()[6]["product"]["tag"] == "SP"

    response = test_client.get("/api/subscriptions?sort=tag,desc")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 7
    assert response.json()[0]["product"]["tag"] == "SP"
    assert response.json()[6]["product"]["tag"] == "IP_PREFIX"

    response = test_client.get("/api/subscriptions?sort=product,asc")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 7
    assert response.json()[0]["product"]["name"] == "INVALID_PRODUCT"
    assert response.json()[6]["product"]["name"] == "PortBProduct"

    response = test_client.get("/api/subscriptions?sort=product,desc")
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 7
    assert response.json()[0]["product"]["name"] == "PortBProduct"
    assert response.json()[6]["product"]["name"] == "INVALID_PRODUCT"


def test_range_subscriptions(seed, test_client):
    response = test_client.get("/api/subscriptions?range=0,3")

    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 3

    response = test_client.get("/api/subscriptions?sort=status,asc&range=5,5")
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_insync_404(seed, test_client):
    response = test_client.get(f"/api/subscriptions/workflows/{str(uuid4())}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_insync_invalid_tagged(seed, test_client):
    response = test_client.get(f"/api/subscriptions/workflows/{INVALID_PORT_SUBSCRIPTION_ID}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "reason": "subscription.not_in_sync",
        "create": [],
        "modify": [],
        "terminate": [],
        "system": [],
    }


def test_parent_subscriptions(seed, test_client):
    response = test_client.get(f"/api/subscriptions/parent_subscriptions/{PORT_A_SUBSCRIPTION_ID}")
    parents = response.json()
    assert len(parents) == 1
    assert SERVICE_SUBSCRIPTION_ID == parents[0]["subscription_id"]


def test_parent_not_insync(seed, test_client):
    # ensure that the parent of the MSP is out of sync
    service = SubscriptionTable.query.get(SERVICE_SUBSCRIPTION_ID)
    service.insync = False
    db.session.commit()

    # test the api endpoint
    response = test_client.get(f"/api/subscriptions/workflows/{PORT_A_SUBSCRIPTION_ID}")
    assert response.status_code == HTTPStatus.OK
    insync_info = response.json()
    assert "reason" in insync_info
    assert len(insync_info["locked_relations"]) == 1
    assert insync_info["locked_relations"][0] == SERVICE_SUBSCRIPTION_ID


def test_parent_insync(seed, test_client):
    response = test_client.get(f"/api/subscriptions/workflows/{PORT_A_SUBSCRIPTION_ID}")
    assert response.status_code == HTTPStatus.OK

    insync_info = response.json()
    assert "reason" not in insync_info
    assert "locked_relations" not in insync_info


def test_child_subscriptions(seed, test_client):
    response = test_client.get(f"/api/subscriptions/child_subscriptions/{SERVICE_SUBSCRIPTION_ID}")
    parents = list(map(lambda sub: sub["subscription_id"], response.json()))
    assert len(parents) == 2

    assert PORT_A_SUBSCRIPTION_ID in parents
    assert SSP_SUBSCRIPTION_ID in parents


def test_child_not_insync(seed, test_client):
    # ensure that the child of the LP is out of sync
    msp = SubscriptionTable.query.with_for_update().get(PORT_A_SUBSCRIPTION_ID)
    msp.insync = False
    db.session.commit()

    # test the api endpoint
    response = test_client.get(f"/api/subscriptions/workflows/{SERVICE_SUBSCRIPTION_ID}")
    assert response.status_code == HTTPStatus.OK
    insync_info = response.json()
    assert "reason" in insync_info
    assert len(insync_info["locked_relations"]) == 1
    assert insync_info["locked_relations"][0] == PORT_A_SUBSCRIPTION_ID


def test_child_insync(seed, test_client):
    response = test_client.get(f"/api/subscriptions/workflows/{SERVICE_SUBSCRIPTION_ID}")
    assert response.status_code == HTTPStatus.OK

    insync_info = response.json()
    assert "reason" not in insync_info
    assert "locked_relations" not in insync_info


def test_delete_subscription(responses, seed, test_client):
    pid = str(uuid4())
    db.session.add(ProcessTable(pid=pid, workflow="statisch_lichtpad_aanvragen", last_status=ProcessStatus.CREATED))
    db.session.add(ProcessSubscriptionTable(pid=pid, subscription_id=PORT_A_SUBSCRIPTION_ID))
    db.session.commit()

    response = test_client.delete(f"/api/subscriptions/{PORT_A_SUBSCRIPTION_ID}")
    assert response.status_code == HTTPStatus.OK

    response = test_client.get("/api/processes")
    assert len(response.json()) == 0


def test_delete_subscription_404(responses, seed, test_client):
    sub_id = uuid4()

    response = test_client.delete(f"/api/subscriptions/{sub_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_subscription_detail_with_domain_model(test_client, generic_subscription_1):
    # test with a subscription that has domain model and without
    response = test_client.get(URL("api/subscriptions/domain-model") / generic_subscription_1)
    assert response.status_code == HTTPStatus.OK
    # Check hierarchy
    assert response.json()["pb_1"]["rt_1"] == "Value1"


def test_other_subscriptions(test_client, generic_subscription_2, generic_product_type_2):
    _, GenericProductTwo = generic_product_type_2
    response = test_client.get(URL("api/subscriptions/instance/other_subscriptions/") / uuid4())
    assert response.status_code == HTTPStatus.NOT_FOUND

    subscription = GenericProductTwo.from_subscription(generic_subscription_2)
    response = test_client.get(
        URL("api/subscriptions/instance/other_subscriptions/") / subscription.pb_3.subscription_instance_id
    )
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 0


def test_set_in_sync(seed, test_client):
    subscription_id = IP_PREFIX_SUBSCRIPTION_ID
    unsync(subscription_id)
    db.session.commit()

    response = test_client.put(f"/api/subscriptions/{subscription_id}/set_in_sync")
    assert response.status_code == HTTPStatus.OK

    subscription = SubscriptionTable.query.get(subscription_id)
    assert subscription.insync


def _create_failed_process(subscription_id):
    pid = uuid4()

    process = ProcessTable(
        pid=pid,
        workflow="validate_ip_prefix",
        last_status=ProcessStatus.FAILED,
        last_step="Verify references in NSO",
        assignee="NOC",
        is_task=False,
    )
    process_subscription = ProcessSubscriptionTable(pid=pid, subscription_id=subscription_id)

    db.session.add(process)
    db.session.add(process_subscription)

    db.session.commit()


def test_try_set_failed_task_in_sync(seed, test_client):
    subscription_id = IP_PREFIX_SUBSCRIPTION_ID
    unsync(IP_PREFIX_SUBSCRIPTION_ID)
    db.session.commit()

    _create_failed_process(subscription_id)

    response = test_client.put(f"/api/subscriptions/{subscription_id}/set_in_sync")
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    subscription = SubscriptionTable.query.get(subscription_id)
    assert not subscription.insync
