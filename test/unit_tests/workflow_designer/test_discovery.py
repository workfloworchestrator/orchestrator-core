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

from orchestrator.core.settings import app_settings
from orchestrator.core.workflow import step
from orchestrator.core.workflow_designer import discovery
from orchestrator.core.workflow_designer.discovery import (
    describe_step,
    discover_steps,
    register_step_package,
    resolve_step,
)
from orchestrator.core.workflows.modify_note import store_subscription_note

STORE_NOTE = "orchestrator.core.workflows.modify_note:store_subscription_note"


def test_describe_core_step():
    info = describe_step(STORE_NOTE, store_subscription_note, product_tags_by_name={})

    assert (info.name, info.function, info.module, info.category, info.kind) == (
        "Store note",
        "store_subscription_note",
        "orchestrator.core.workflows.modify_note",
        "general",
        "step",
    )
    assert [(i.name, i.type.kind, i.required) for i in info.inputs] == [
        ("subscription_id", "uuid", True),
        ("note", "str", True),
    ]
    assert [o.key for o in info.outputs] == ["subscription"]
    assert info.usable


@step("Needs whole state")
def needs_whole_state(state: dict) -> dict:
    return {}


@step("Takes kwargs")
def takes_kwargs(**kwargs: str) -> dict:
    return {}


@pytest.mark.parametrize(
    ("step_object", "reason"),
    [
        pytest.param(needs_whole_state, "reads the whole state", id="whole-state"),
        pytest.param(takes_kwargs, "takes *args/**kwargs", id="kwargs"),
    ],
)
def test_describe_unusable_step(step_object, reason):
    info = describe_step("m:s", step_object, product_tags_by_name={})

    assert not info.usable
    assert reason in info.unusable_reason


@pytest.mark.parametrize(
    ("packages", "module", "category"),
    [
        pytest.param(
            ["orchestrator.core.workflows"], "orchestrator.core.workflows.modify_note", "general", id="top-level"
        ),
        pytest.param(
            ["orchestrator.core.workflows"], "orchestrator.core.workflows.tasks.cleanup", "tasks", id="sub-package"
        ),
        pytest.param(
            ["app.workflows", "app.workflows.l2"], "app.workflows.l2.vpn.create", "vpn", id="longest-package-wins"
        ),
        pytest.param(["app.workflows"], "elsewhere.module", "elsewhere", id="outside-packages"),
    ],
)
def test_category(monkeypatch, packages, module, category):
    monkeypatch.setattr(app_settings, "WORKFLOW_DESIGNER_STEP_PACKAGES", packages)

    assert discovery._category(module) == category


@pytest.mark.parametrize(
    ("step_id", "found"),
    [
        pytest.param(STORE_NOTE, True, id="step"),
        pytest.param("orchestrator.core.workflows.modify_note:initial_input_form", False, id="not-a-step"),
        pytest.param("orchestrator.core.workflows.modify_note:does_not_exist", False, id="missing-attribute"),
        pytest.param("orchestrator.core.no_such_module:step", False, id="missing-module"),
    ],
)
def test_resolve_step(no_step_scan_cache, step_id, found):
    assert (resolve_step(step_id) is store_subscription_note) is found


def test_discover_core_steps(no_step_scan_cache):
    steps = discover_steps(product_tags=dict)

    assert STORE_NOTE in steps
    assert steps[STORE_NOTE].used_in_workflows == ["modify_note"]
    # Cached until a rescan.
    assert discover_steps(product_tags=dict) is steps
    assert discover_steps(rescan=True, product_tags=dict) is not steps


def test_register_step_package_invalidates_the_scan(monkeypatch, no_step_scan_cache):
    monkeypatch.setattr(app_settings, "WORKFLOW_DESIGNER_STEP_PACKAGES", ["orchestrator.core.workflows"])
    steps = discover_steps(product_tags=dict)

    register_step_package("orchestrator.core.workflows")
    assert discover_steps(product_tags=dict) is steps

    register_step_package("test.unit_tests.workflow_designer")
    assert app_settings.WORKFLOW_DESIGNER_STEP_PACKAGES[-1] == "test.unit_tests.workflow_designer"
    rescanned = discover_steps(product_tags=dict)
    assert rescanned is not steps
    assert "test.unit_tests.workflow_designer.test_discovery:needs_whole_state" in rescanned
