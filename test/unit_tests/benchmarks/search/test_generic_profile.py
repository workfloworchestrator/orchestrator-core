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

from test.benchmarks.search.corpus import DESCRIPTION, IDENTIFIER, LOCATION
from test.benchmarks.search.profiles.generic import (
    IP_PEERING,
    L2VPN,
    LIGHT_PATH,
    LR,
    NWR,
    PREFIX,
    RUG,
    SERVICE_PORT,
    End,
    GenericProfile,
    Peering,
    Spec,
)

AMS = End("Amsterdam", "ams", 1, 1, "et-0/0/1", 101)
RTD = End("Rotterdam", "rtd", 1, 2, "et-0/0/2", 101)
PEERING = Peering(prefix="192.0.2.0/24", asn=64500)


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


@pytest.mark.parametrize(
    "product, ends, kwargs",
    [
        (SERVICE_PORT, [AMS], {}),
        (LIGHT_PATH, [AMS, RTD], {}),
        (L2VPN, [AMS, RTD, AMS, RTD], {}),
        (IP_PEERING, [AMS], {"peering": PEERING}),
        (PREFIX, [], {"prefix": "192.0.2.0/24"}),
        (LR, [AMS, RTD, AMS, RTD], {}),
    ],
)
def test_spec_accepts_what_its_product_takes(product, ends, kwargs):
    assert Spec("key", product, NWR, ends, **kwargs).product == product


def test_redundant_light_path_splits_its_ends_per_vc():
    assert Spec("key", LR, RUG, [AMS, RTD, RTD, AMS]).vcs == [[AMS, RTD], [RTD, AMS]]


@pytest.mark.parametrize("product", [SERVICE_PORT, LIGHT_PATH])
def test_other_products_keep_their_ends_in_one_vc(product):
    ends = [AMS, RTD][: product.max_ends]

    assert Spec("key", product, NWR, ends).vcs == [ends]


@pytest.mark.parametrize(
    "key, description, identifiers, locations",
    [
        ("ams001a-rt01", "NWR SP UNTAGGED AMS001A 10 Gbit/s", ("ams001a-rt01",), ("Amsterdam",)),
        (
            "northwind-lightpath",
            "NWR LP AMS001A-RTD001A 10 Gbit/s",
            ("ams001a-rt07", "rtd001a-rt07"),
            ("Amsterdam", "Rotterdam"),
        ),
        ("northwind-peering", "NWR IP UTR001A 10 Gbit/s", ("utr001a-rt02",), ("Utrecht",)),
        (
            "rtd001a-rt01",
            "SLM L2VPN EHV001A-RTD001A 10 Gbit/s",
            ("rtd001a-rt01", "ehv001a-rt03"),
            ("Rotterdam", "Eindhoven"),
        ),
        ("rug-prefix-lir", "RUG prefix LIR 192.87.22.0/24", ("192.87.22.0/24",), ()),
        (
            "rug-lr",
            "RUG LR ASD001B-GN012A ASD002A-GN001B 10 Gbit/s",
            ("asd001b-rt01", "gn012a-rt01", "asd002a-rt01", "gn001b-rt01"),
            ("Assen", "Groningen", "Assen", "Groningen"),
        ),
    ],
)
def test_anchor_facts_are_as_the_hand_written_queries_expect(key, description, identifiers, locations):
    facts = {anchor.key: anchor.facts for anchor in GenericProfile().anchors()}[key]

    assert facts[DESCRIPTION] == (description,)
    assert facts[IDENTIFIER] == identifiers
    assert facts[LOCATION] == locations


def test_anchors_carry_the_blocks_of_their_product():
    models = {anchor.key: anchor.model for anchor in GenericProfile().anchors()}

    assert models["ams001a-rt01"].port is not None
    assert models["northwind-lightpath"].vc is not None
    assert models["northwind-peering"].ip_peering is not None
    assert models["rug-prefix-lir"].ip_prefix is not None
    assert models["rug-lr"].lrss is not None
    assert len(models["rug-lr"].lrss.vcs) == 2
    assert (
        models["rug-lr"].lrss.vcs[0].subscription_instance_id != models["rug-lr"].lrss.vcs[1].subscription_instance_id
    )
