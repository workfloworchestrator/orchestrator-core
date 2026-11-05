# Copyright 2019-2026 SURF, GÉANT.
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

import pytest

from test.benchmarks.search.profiles.network_services import (
    IP_PEERING,
    L2VPN,
    LIGHT_PATH,
    LR,
    NWR,
    PREFIX,
    RUG,
    SERVICE_PORT,
    End,
    NetworkServicesProfile,
    Spec,
)

AMS = End("Amsterdam", "ams", 1, 1, "et-0/0/1", 101)
RTD = End("Rotterdam", "rtd", 1, 2, "et-0/0/2", 101)


@pytest.mark.parametrize(
    "product, ends, kwargs, match",
    [
        (SERVICE_PORT, [], {}, "takes 1 to 1 ends"),
        (SERVICE_PORT, [AMS, RTD], {}, "takes 1 to 1 ends"),
        (LIGHT_PATH, [AMS], {}, "takes 2 to 2 ends"),
        (L2VPN, [AMS, RTD, AMS, RTD, AMS], {}, "takes 2 to 4 ends"),
        (LR, [AMS, RTD], {}, "takes 4 to 4 ends"),
        (PREFIX, [AMS], {"prefix": "192.0.2.0/24"}, "takes 0 to 0 ends"),
        (IP_PEERING, [AMS], {}, "needs a peering"),
        (PREFIX, [], {}, "needs a prefix"),
    ],
)
def test_spec_rejects_what_its_product_cannot_take(product, ends, kwargs, match):
    with pytest.raises(ValueError, match=match):
        Spec("key", product, NWR, ends, **kwargs)


def test_redundant_light_path_splits_its_ends_per_vc():
    assert Spec("key", LR, RUG, [AMS, RTD, RTD, AMS]).vcs == [[AMS, RTD], [RTD, AMS]]


def test_anchors_carry_the_blocks_of_their_product():
    models = {anchor.key: anchor.model for anchor in NetworkServicesProfile().anchors()}

    assert models["ams001a-rt01"].port is not None
    assert models["northwind-lightpath"].vc is not None
    assert models["northwind-peering"].ip_peering is not None
    assert models["rug-prefix-lir"].ip_prefix is not None
    assert models["rug-lr"].lrss is not None
    assert len(models["rug-lr"].lrss.vcs) == 2
    assert (
        models["rug-lr"].lrss.vcs[0].subscription_instance_id != models["rug-lr"].lrss.vcs[1].subscription_instance_id
    )
