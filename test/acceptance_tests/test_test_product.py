# Copyright 2019-2026 ESnet, GÉANT, SURF.
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

from ipaddress import IPv4Address, IPv6Address
from uuid import uuid4

import pytest

from test.acceptance_tests.fixtures.test_orchestrator.devtools.populator.test_product_populator import (
    TestProductPopulator,
)


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
