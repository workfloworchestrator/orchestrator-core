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

from typing import Literal
from uuid import UUID

import pytest

from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.core.domain.base import SubscriptionModel
from orchestrator.core.types import SubscriptionLifecycle
from orchestrator.core.workflow_designer.type_refs import TypeRef, check, type_ref_for
from pydantic_forms.types import UUIDstr


class IntIdBase:
    pass


class SomeIntId(IntIdBase):
    """Wrapped ids declare their primitive as a generic argument somewhere up the MRO."""

    __orig_bases__ = (tuple[int],)

    def unwrap(self) -> int:
        return 1


class PortInactive(SubscriptionModel, is_base=True):
    pass


class PortProvisioning(PortInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
    pass


class Port(PortProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    pass


@pytest.fixture
def port_products(monkeypatch):
    monkeypatch.setitem(SUBSCRIPTION_MODEL_REGISTRY, "Port 10G", Port)
    monkeypatch.setitem(SUBSCRIPTION_MODEL_REGISTRY, "Port 1G", Port)
    return {"Port 10G": "PORT", "Port 1G": "PORT", "Other": "OTHER"}


@pytest.mark.parametrize(
    ("annotation", "source", "param", "expected"),
    [
        pytest.param(str, "str", "zone", TypeRef(kind="str"), id="str"),
        pytest.param(UUIDstr, "UUIDstr", "anything", TypeRef(kind="uuid"), id="uuidstr-by-source"),
        pytest.param(str, "str", "subscription_id", TypeRef(kind="uuid"), id="uuid-by-param-name"),
        pytest.param(UUID | None, None, "x", TypeRef(kind="uuid", optional=True), id="optional-uuid"),
        pytest.param(list[dict], None, "x", TypeRef(kind="list"), id="list"),
        pytest.param(dict[str, int], None, "x", TypeRef(kind="dict"), id="dict"),
        pytest.param(bool, None, "x", TypeRef(kind="bool"), id="bool-not-int"),
        pytest.param(Literal["a", "b"], None, "x", TypeRef(kind="str"), id="str-literal"),
        pytest.param(SomeIntId, None, "x", TypeRef(kind="int"), id="wrapped-int-id"),
        pytest.param(int | str, None, "x", TypeRef(), id="union-is-any"),
        pytest.param(SubscriptionModel, None, "x", TypeRef(kind="subscription"), id="any-subscription"),
    ],
)
def test_type_ref_for(annotation, source, param, expected):
    assert type_ref_for(annotation, source, param) == expected


@pytest.mark.parametrize(
    ("model", "statuses"),
    [
        pytest.param(Port, ["active"], id="active-model"),
        pytest.param(PortProvisioning, ["provisioning"], id="provisioning-model"),
    ],
)
def test_type_ref_for_subscription_model_restricts_products_and_lifecycles(port_products, model, statuses):
    ref = type_ref_for(model, product_tags_by_name=port_products)

    assert ref == TypeRef(kind="subscription", model=model.__name__, product_tags=["PORT"], statuses=statuses)


@pytest.mark.parametrize(
    ("provided", "required", "severity"),
    [
        pytest.param(TypeRef(kind="str"), TypeRef(kind="str"), "ok", id="same"),
        pytest.param(TypeRef(kind="uuid"), TypeRef(kind="str"), "ok", id="uuid-as-str"),
        pytest.param(TypeRef(kind="int"), TypeRef(kind="float"), "ok", id="int-as-float"),
        pytest.param(TypeRef(kind="str"), TypeRef(kind="uuid"), "warning", id="str-maybe-uuid"),
        pytest.param(TypeRef(kind="bool"), TypeRef(kind="list"), "error", id="bool-not-list"),
        pytest.param(TypeRef(), TypeRef(kind="int"), "warning", id="unknown-provided"),
        pytest.param(TypeRef(kind="int"), TypeRef(), "ok", id="any-required"),
        pytest.param(TypeRef(kind="str", optional=True), TypeRef(kind="str"), "warning", id="maybe-empty"),
        pytest.param(TypeRef(kind="str", optional=True), TypeRef(kind="str", optional=True), "ok", id="both-optional"),
        pytest.param(TypeRef(kind="subscription"), TypeRef(kind="uuid"), "ok", id="subscription-as-id"),
        pytest.param(
            TypeRef(kind="subscription"),
            TypeRef(kind="subscription", model="Sp", product_tags=["SP"]),
            "error",
            id="unrestricted-picker-for-model",
        ),
        pytest.param(
            TypeRef(kind="subscription", product_tags=["SP", "LP"]),
            TypeRef(kind="subscription", model="Sp", product_tags=["SP"]),
            "error",
            id="picker-allows-other-product",
        ),
        pytest.param(
            TypeRef(kind="subscription", product_tags=["SP"]),
            TypeRef(kind="subscription", model="Sp", product_tags=["SP"], statuses=["active"]),
            "ok",
            id="matching-picker",
        ),
        pytest.param(
            TypeRef(kind="subscription", product_tags=["SP"], statuses=["active", "initial"]),
            TypeRef(kind="subscription", model="Sp", product_tags=["SP"], statuses=["active"]),
            "error",
            id="picker-allows-other-lifecycle",
        ),
    ],
)
def test_check(provided, required, severity):
    assert check(provided, required).severity == severity
