from http import HTTPStatus
from ipaddress import IPv4Address
from unittest import mock
from uuid import uuid4

import pytest

from nwastdlib.url import URL
from orchestrator.api.helpers import product_block_paths
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
from orchestrator.db.models import SubscriptionInstanceRelationTable, WorkflowTable
from orchestrator.domain.base import SubscriptionModel
from orchestrator.services.subscriptions import (
    RELATION_RESOURCE_TYPES,
    _generate_etag,
    build_extended_domain_model,
    get_subscription,
    unsync,
)
from orchestrator.targets import Target
from orchestrator.workflow import ProcessStatus
from test.unit_tests.config import (
    IMS_CIRCUIT_ID,
    INTERNETPINNEN_PREFIX_SUBSCRIPTION_ID,
    IPAM_PREFIX_ID,
    PARENT_IP_PREFIX_SUBSCRIPTION_ID,
    PEER_GROUP_SUBSCRIPTION_ID,
    PORT_SUBSCRIPTION_ID,
)
from test.unit_tests.conftest import do_refresh_subscriptions_search_view

SERVICE_SUBSCRIPTION_ID = str(uuid4())
PORT_A_SUBSCRIPTION_ID = str(uuid4())
PORT_A_SUBSCRIPTION_BLOCK_ID = str(uuid4())
PROVISIONING_PORT_A_SUBSCRIPTION_ID = str(uuid4())
SSP_SUBSCRIPTION_ID = str(uuid4())
SSP_SUBSCRIPTION_BLOCK_ID = str(uuid4())
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
        tag="LightPath",  # This is special since in_use_by/depends_on subscription code handles specific tags
        status="active",
        product_blocks=product_blocks,
        fixed_inputs=fixed_inputs,
    )
    port_a_product = ProductTable(
        product_id=PRODUCT_ID,
        name="PortAProduct",
        description="Port A description",
        product_type="Port",
        tag="SP",  # This is special since in_use_by/depends_on subscription code handles specific tags
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
            PEER_GROUP_SUBSCRIPTION_ID,
        ]
    )

    return ip_prefix_product


# seeder to test direct relations using SubscriptionInstanceRelationTable instead of resource type.
@pytest.fixture
def seed_with_direct_relations():
    # These resource types are special
    resources = [
        ResourceTypeTable(resource_type=IMS_CIRCUIT_ID, description="Desc"),
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
        tag="LightPath",  # This is special since in_use_by/depends_on subscription code handles specific tags
        status="active",
        product_blocks=product_blocks,
        fixed_inputs=fixed_inputs,
    )
    port_a_product = ProductTable(
        product_id=PRODUCT_ID,
        name="PortAProduct",
        description="Port A description",
        product_type="Port",
        tag="SP",  # This is special since in_use_by/depends_on subscription code handles specific tags
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
                subscription_instance_id=PORT_A_SUBSCRIPTION_BLOCK_ID,
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
                subscription_instance_id=SSP_SUBSCRIPTION_BLOCK_ID,
                product_block=product_blocks[0],
                values=[SubscriptionInstanceValueTable(resource_type=resources[0], value="54321")],
            )
        ],
    )

    lp_subscription_instance_ssp_id = str(uuid4())
    lp_subscription_instance_values_ssp = [
        SubscriptionInstanceValueTable(resource_type=resources[0], value="54321"),
    ]
    lp_subscription_instance_ssp = SubscriptionInstanceTable(
        subscription_instance_id=lp_subscription_instance_ssp_id,
        product_block=product_blocks[0],
        values=lp_subscription_instance_values_ssp,
    )
    lp_subscription_instance_ssp_depends_on = SubscriptionInstanceRelationTable(
        in_use_by_id=lp_subscription_instance_ssp_id,
        depends_on_id=PORT_A_SUBSCRIPTION_BLOCK_ID,
        order_id=0,
        domain_model_attr="service_port",
    )

    lp_subscription_instance_msp_id = str(uuid4())
    lp_subscription_instance_values_msp = [
        SubscriptionInstanceValueTable(resource_type=resources[0], value="54321"),
    ]
    lp_subscription_instance_msp = SubscriptionInstanceTable(
        subscription_instance_id=lp_subscription_instance_msp_id,
        product_block=product_blocks[0],
        values=lp_subscription_instance_values_msp,
    )
    lp_subscription_instance_msp_depends_on = SubscriptionInstanceRelationTable(
        in_use_by_id=lp_subscription_instance_msp_id,
        depends_on_id=SSP_SUBSCRIPTION_BLOCK_ID,
        order_id=0,
        domain_model_attr="service_port",
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
    db.session.add(lp_subscription_instance_ssp_depends_on)
    db.session.add(lp_subscription_instance_msp_depends_on)
    db.session.commit()

    RELATION_RESOURCE_TYPES.extend(
        [
            PORT_SUBSCRIPTION_ID,
            IP_PREFIX_SUBSCRIPTION_ID,
            INTERNETPINNEN_PREFIX_SUBSCRIPTION_ID,
            PARENT_IP_PREFIX_SUBSCRIPTION_ID,
            PEER_GROUP_SUBSCRIPTION_ID,
        ]
    )

    return ip_prefix_product


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
        "validate": [],
    }


def test_in_use_by_subscriptions_not_insync(seed, test_client):
    # ensure that the used subscription of the MSP is out of sync
    service = get_subscription(SERVICE_SUBSCRIPTION_ID)
    service.insync = False
    db.session.commit()

    # test the api endpoint
    response = test_client.get(f"/api/subscriptions/workflows/{PORT_A_SUBSCRIPTION_ID}")
    assert response.status_code == HTTPStatus.OK
    insync_info = response.json()
    assert "reason" in insync_info
    assert len(insync_info["locked_relations"]) == 1
    assert insync_info["locked_relations"][0] == SERVICE_SUBSCRIPTION_ID


def test_in_use_by_subscriptions_insync(seed, test_client):
    response = test_client.get(f"/api/subscriptions/workflows/{PORT_A_SUBSCRIPTION_ID}")
    assert response.status_code == HTTPStatus.OK

    insync_info = response.json()
    assert "reason" not in insync_info
    assert "locked_relations" not in insync_info


def test_depends_on_subscriptions_not_insync(seed, test_client):
    # ensure that the depends on subscription of the LP is out of sync
    msp = db.session.get(SubscriptionTable, PORT_A_SUBSCRIPTION_ID, with_for_update=True)
    msp.insync = False
    db.session.commit()

    # test the api endpoint
    response = test_client.get(f"/api/subscriptions/workflows/{SERVICE_SUBSCRIPTION_ID}")
    assert response.status_code == HTTPStatus.OK
    insync_info = response.json()
    assert "reason" in insync_info
    assert len(insync_info["locked_relations"]) == 1
    assert insync_info["locked_relations"][0] == PORT_A_SUBSCRIPTION_ID


def test_depends_on_subscriptions_insync(seed, test_client):
    response = test_client.get(f"/api/subscriptions/workflows/{SERVICE_SUBSCRIPTION_ID}")
    assert response.status_code == HTTPStatus.OK

    insync_info = response.json()
    assert "reason" not in insync_info
    assert "locked_relations" not in insync_info


def test_in_use_by_subscriptions_not_insync_direct_relations(seed_with_direct_relations, test_client):
    # ensure that the used subscription of the MSP is out of sync
    service = get_subscription(SERVICE_SUBSCRIPTION_ID)
    service.insync = False
    db.session.commit()

    # test the api endpoint
    response = test_client.get(f"/api/subscriptions/workflows/{PORT_A_SUBSCRIPTION_ID}")
    assert response.status_code == HTTPStatus.OK
    insync_info = response.json()
    assert "reason" in insync_info
    assert len(insync_info["locked_relations"]) == 1
    assert insync_info["locked_relations"][0] == SERVICE_SUBSCRIPTION_ID


def test_depends_on_subscriptions_not_insync_direct_relations(seed_with_direct_relations, test_client):
    # ensure that the depends on subscription of the LP is out of sync
    msp = get_subscription(PORT_A_SUBSCRIPTION_ID, for_update=True)
    msp.insync = False
    db.session.commit()

    # test the api endpoint
    response = test_client.get(f"/api/subscriptions/workflows/{SERVICE_SUBSCRIPTION_ID}")
    assert response.status_code == HTTPStatus.OK
    insync_info = response.json()
    assert "reason" in insync_info
    assert len(insync_info["locked_relations"]) == 1
    assert insync_info["locked_relations"][0] == PORT_A_SUBSCRIPTION_ID


def test_depends_on_subscriptions_insync_direct_relations(seed_with_direct_relations, test_client):
    response = test_client.get(f"/api/subscriptions/workflows/{SERVICE_SUBSCRIPTION_ID}")
    assert response.status_code == HTTPStatus.OK

    insync_info = response.json()
    assert "reason" not in insync_info
    assert "locked_relations" not in insync_info


def test_delete_subscription_404(responses, seed, test_client):
    sub_id = uuid4()

    response = test_client.delete(f"/api/subscriptions/{sub_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_set_in_sync(seed, test_client):
    subscription_id = IP_PREFIX_SUBSCRIPTION_ID
    unsync(subscription_id)
    db.session.commit()

    response = test_client.put(f"/api/subscriptions/{subscription_id}/set_in_sync")
    assert response.status_code == HTTPStatus.OK

    subscription = get_subscription(subscription_id)
    assert subscription.insync


def _create_failed_process(subscription_id):
    wf = WorkflowTable(
        workflow_id=uuid4(), name="validate_ip_prefix", description="validate_ip_prefix", target=Target.SYSTEM
    )
    process_id = uuid4()
    process = ProcessTable(
        process_id=process_id,
        workflow_id=wf.workflow_id,
        last_status=ProcessStatus.FAILED,
        last_step="Verify references in NSO",
        assignee="NOC",
        is_task=False,
    )
    process_subscription = ProcessSubscriptionTable(process_id=process_id, subscription_id=subscription_id)
    db.session.add(wf)
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

    subscription = get_subscription(subscription_id)
    assert not subscription.insync


def test_product_block_paths(generic_subscription_1, generic_subscription_2):
    subscription_1 = SubscriptionModel.from_subscription(generic_subscription_1)
    subscription_2 = SubscriptionModel.from_subscription(generic_subscription_2)
    assert product_block_paths(subscription_1) == ["product", "pb_1", "pb_2"]
    assert product_block_paths(subscription_2) == ["product", "pb_3"]


@pytest.mark.parametrize(
    "query, num_matches",
    [
        ("id", 7),
        ("tag:(POR* | LP)", 1),
        ("tag:SP", 3),
        ("tag:(POR* | LP) | tag:SP", 4),
        ("tag:(POR* | LP) | tag:SP -status:initial", 3),
    ],
)
def test_subscriptions_search(query, num_matches, seed, test_client, refresh_subscriptions_search_view):
    response = test_client.get(f"/api/subscriptions/search?query={query}")
    result = response.json()
    assert len(result) == num_matches


@pytest.fixture
def make_port_subscription():

    def make(subscription_id=None, customer_id=None, product_id=None):
        product_id = str(product_id or uuid4())
        subscription_id = str(subscription_id or uuid4())
        customer_id = str(customer_id or uuid4())
        product = ProductTable(
            product_id=product_id,
            name="ProductTable",
            description="description",
            product_type="Port",
            tag="Port",
            status="active",
        )
        subscription = SubscriptionTable(
            subscription_id=subscription_id,
            description="desc",
            status="active",
            insync=True,
            product=product,
            customer_id=customer_id,
        )

        db.session.add(product)
        db.session.add(subscription)
        db.session.commit()
        do_refresh_subscriptions_search_view()
        return subscription_id, customer_id, product_id

    return make


@pytest.mark.parametrize(
    "subscription_id",
    [
        "144cd85c-77a9-43bf-a78c-3ef2647c6ff1",
        "67bb12ae-8dfc-4ddb-9fd2-979392a9f2ad",
        "85ab4e94-c045-46f3-85c7-a8fbc7411aca",
        "27e84752-c700-491e-b126-454b5fa06dc0",
        "191b9852-e689-4dd2-8699-fc9c11c2bcdd",
        "998e7c12-e4d2-4321-a075-04b13a76ab39",
        "cfc64927-8f52-4325-87ac-daa1e16794e8",
        "5846383e-6387-411b-8e6e-bca022e2a86d",
    ],
)
def test_subscriptions_search_uuids2(
    subscription_id, make_port_subscription, test_client, refresh_subscriptions_search_view
):
    make_port_subscription(subscription_id=subscription_id)

    search_queries = {"full": subscription_id} | {
        f"group{n}": part for n, part in enumerate(subscription_id.split("-"))
    }

    def search(keyword):
        response = test_client.get(f"/api/subscriptions/search?query={keyword}")
        return len(response.json()) == 1

    results = {testcase: search(keyword) for testcase, keyword in search_queries.items()}

    succeeded = [search_queries[testcase] for testcase in results if results[testcase]]
    failed = [search_queries[testcase] for testcase in results if not results[testcase]]

    assert not failed, f"Could not find '{subscription_id}' by all keywords; {succeeded=} {failed=}"


def test_subscription_detail_with_domain_model(test_client, generic_subscription_1, benchmark, monitor_sqlalchemy):
    # test with a subscription that has domain model and without
    with monitor_sqlalchemy():

        @benchmark
        def response():
            return test_client.get(URL("api/subscriptions/domain-model") / generic_subscription_1)

    assert response.status_code == HTTPStatus.OK
    # Check hierarchy
    assert response.json()["pb_1"]["rt_1"] == "Value1"


def test_subscription_detail_with_domain_model_does_not_exist(test_client, generic_subscription_1, benchmark):
    # test with a subscription that has domain model and without
    @benchmark
    def response():
        return test_client.get(URL("api/subscriptions/domain-model") / uuid4())

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_subscription_detail_with_domain_model_etag(test_client, generic_subscription_1):
    # test with a subscription that has domain model and without
    response = test_client.get(URL("api/subscriptions/domain-model") / generic_subscription_1)
    assert response.status_code == HTTPStatus.OK
    subscription = SubscriptionModel.from_subscription(generic_subscription_1)
    extended_model = build_extended_domain_model(subscription)
    etag = _generate_etag(extended_model)
    assert etag == response.headers["ETag"]
    # Check hierarchy
    assert response.json()["pb_1"]["rt_1"] == "Value1"


def test_subscription_detail_with_domain_model_if_none_match(test_client, generic_subscription_1):
    # test with a subscription that has domain model and without
    subscription = SubscriptionModel.from_subscription(generic_subscription_1)
    extended_model = build_extended_domain_model(subscription)
    etag = _generate_etag(extended_model)
    response = test_client.get(
        URL("api/subscriptions/domain-model") / generic_subscription_1, headers={"If-None-Match": etag}
    )
    assert response.status_code == HTTPStatus.NOT_MODIFIED


def test_subscription_detail_with_in_use_by_ids_filtered_self(test_client, product_one_subscription_1):
    response = test_client.get(URL("api/subscriptions/domain-model") / product_one_subscription_1)
    assert response.status_code == HTTPStatus.OK
    assert not response.json()["block"]["sub_block"]["in_use_by_ids"]


@mock.patch("orchestrator.api.api_v1.endpoints.subscriptions.get_subscription_dict")
def test_subscription_detail_special_fields(mock_from_redis, test_client):
    """Test that a subscription with special field types is correctly serialized by Pydantic.

    https://github.com/pydantic/pydantic/issues/6669
    """
    standard_fields = {
        "subscription_id": "fabd6359-cb37-4a1c-bfc4-5c15aea7c888",
        "description": "desc",
        "status": "active",
        "customer_id": "f711c6fe-6de3-40bd-a4e7-9ac9d183a788",
        "insync": True,
        "version": 1,
        "product": {
            "name": "fake name",
            "description": "fake description",
            "product_type": "fake type",
            "status": "active",
            "tag": "fake tag",
        },
    }
    # Make the from_redis function return an IPv4Address - this wouldn't happen normally but it's easier
    # to mock than SubscriptionModel.from_subscription, and tests the special field formatting all the same
    special_fields = {"ip_address": IPv4Address("127.0.0.1")}
    mock_from_redis.return_value = (standard_fields | special_fields, "etag ofzo")

    response = test_client.get(URL("api/subscriptions/domain-model") / "fabd6359-cb37-4a1c-bfc4-5c15aea7c888")
    assert response.json() == {
        "subscription_id": "fabd6359-cb37-4a1c-bfc4-5c15aea7c888",
        "start_date": None,
        "description": "desc",
        "status": "active",
        "product_id": None,
        "customer_id": "f711c6fe-6de3-40bd-a4e7-9ac9d183a788",
        "insync": True,
        "note": None,
        "name": None,
        "end_date": None,
        "product": {
            "product_id": None,
            "name": "fake name",
            "description": "fake description",
            "product_type": "fake type",
            "status": "active",
            "tag": "fake tag",
            "created_at": None,
            "end_date": None,
        },
        "customer_descriptions": [],
        "tag": None,
        "version": 1,
        "ip_address": "127.0.0.1",
    }


def test_subscription_detail_with_in_use_by_ids_not_filtered_self(test_client, product_one_subscription_1):
    response = test_client.get(
        URL("api/subscriptions/domain-model") / product_one_subscription_1 / "?filter_owner_relations=false"
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()["block"]["sub_block"]["in_use_by_ids"]
