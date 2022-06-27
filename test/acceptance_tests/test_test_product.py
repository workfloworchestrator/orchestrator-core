from ipaddress import IPv4Address, IPv6Address
from uuid import uuid4

import pytest

from test_orchestrator.devtools.populator.test_product_populator import TestProductPopulator


@pytest.mark.acceptance
def test_test_product(new_test_product):
    populator = TestProductPopulator(
        an_int=1,
        a_str="string",
        a_bool=False,
        an_uuid=str(uuid4()),
        an_ipv4=IPv4Address("10.0.0.1"),
        an_ipv6=IPv6Address("::cafe:babe:feed:face:dead:beef"),
    )

    populator.start_create_workflow()
    populator.run()

    # validate = "validate_test_product"
    # populator.start_verify_workflow(validate, subscription_id)
    # populator.run()

    # populator.start_terminate_workflow(subscription_id)
    # populator.run()
