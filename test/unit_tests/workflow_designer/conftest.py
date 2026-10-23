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

from orchestrator.core.workflow_designer import discovery
from orchestrator.core.workflow_designer.forms import FIELD_TYPES, FieldOptions, FieldType
from orchestrator.core.workflow_designer.type_refs import TypeRef


@pytest.fixture(autouse=True)
def isolated_field_types(monkeypatch):
    """Field types registered by a test (or an application) must not leak into other tests."""
    monkeypatch.setattr("orchestrator.core.workflow_designer.forms.FIELD_TYPES", dict(FIELD_TYPES))


@pytest.fixture
def subscription_field_type(monkeypatch):
    """A subscription selector like the one an application registers; core has none of its own."""

    def suggest(name: str, ref: TypeRef) -> FieldOptions | None:
        if ref.kind == "subscription" or (ref.kind == "uuid" and name.endswith("subscription_id")):
            return FieldOptions(product_tags=ref.product_tags, statuses=ref.statuses)
        return None

    field_type = FieldType(
        "subscription",
        "Subscription",
        lambda _: str,
        lambda options: TypeRef(kind="subscription", product_tags=options.product_tags, statuses=options.statuses),
        ["product_tags", "statuses"],
        suggest=suggest,
    )
    from orchestrator.core.workflow_designer import forms

    forms.register_field_type(field_type)
    return field_type


@pytest.fixture
def no_step_scan_cache():
    discovery._cache = None
    discovery._objects.clear()
    yield
    discovery._cache = None
    discovery._objects.clear()
