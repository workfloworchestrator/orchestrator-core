from dataclasses import dataclass
from typing import Optional


@dataclass
class ImsPort:
    node_id: int
    status: int
    iface_type: str
    node: str


@dataclass
class ImsNode:
    location: str
    status: str
    id: Optional[int]


IP_PREFIX_NAME = "IP Prefix"

IP_PREFIX_PRODUCT_ID = "2b2125f2-a074-4e44-8d4b-edc677381d46"
IPBGP_PRODUCT_ID = "876125f2-a074-4e44-8d4b-edc677381d46"
IPS_PRODUCT_ID = "456125f2-a074-4e44-8d4b-edc677381d46"
SP_PRODUCT_ID = "6911deed-e2b5-4038-9fca-6cb7bc6c07d3"
AGGSP_PRODUCT_ID = "1367deed-e2b5-4038-9fca-6cb7bc6c07d3"

IP_PREFIX_SUB_ID = "e89776be-16c3-4bee-af98-8e73bf6492a7"
IPS_SUB_ID = "abc776be-16c3-4bee-af98-8e73bf6492a7"
IPBGP_SUB_ID = "123776be-16c3-4bee-af98-8e73bf6492a7"
MISSING_SUB_ID = "00e651c6-e16a-4ff6-8f21-af78ff199faf"
TAGGED_SUB_ID = "b2791099-86a3-4754-b70b-529bf1126246"
UNTAGGED_SUB_ID = "de6bcd9a-e003-49b0-a5e0-0bf43f747d80"
AGGSP_SUB_ID = "1858cd9a-e003-49b0-a5e0-0bf43f747d80"

CUSTOMER_ID1 = "1f2c4fae-77ab-4edf-b67a-f99ad3e49ad1"


PRODUCT_TO_TAG = {
    IP_PREFIX_PRODUCT_ID: "IP_PREFIX",
    IPBGP_PRODUCT_ID: "IPBGP",
    IPS_PRODUCT_ID: "IPS",
    SP_PRODUCT_ID: "SP",
    AGGSP_PRODUCT_ID: "AGGSP",
}

SUB_TO_PRODUCT = {
    IP_PREFIX_SUB_ID: IP_PREFIX_PRODUCT_ID,
    IPS_SUB_ID: IPS_PRODUCT_ID,
    IPBGP_SUB_ID: IPBGP_PRODUCT_ID,
    MISSING_SUB_ID: IP_PREFIX_PRODUCT_ID,
    TAGGED_SUB_ID: SP_PRODUCT_ID,
    UNTAGGED_SUB_ID: SP_PRODUCT_ID,
    AGGSP_SUB_ID: AGGSP_PRODUCT_ID,
}
