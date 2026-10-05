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

import asyncio

import pytest

from orchestrator.core.settings import get_authorizers
from orchestrator.core.targets import Target
from orchestrator.core.utils.auth import AuthContext
from orchestrator.core.utils.functional import orig
from orchestrator.core.workflow_designer import builder
from orchestrator.core.workflow_designer.builder import (
    build_invalid_workflow,
    build_step,
    build_workflow,
    set_authorizer_factory,
)
from orchestrator.core.workflow_designer.definition import StepRef, WorkflowDefinition
from orchestrator.core.workflow_designer.forms import FormField

DEFINITION = WorkflowDefinition(
    name="designed_note",
    description="Store a note",
    form_fields=[FormField(name="subscription_id", type="uuid"), FormField(name="note", type="string")],
    steps=[
        StepRef(step_id="orchestrator.core.workflows.modify_note:store_subscription_note"),
        StepRef(step_id="designer:set_value", config={"key": "checked_by", "value": "designer"}),
    ],
)


@pytest.fixture(autouse=True)
def no_authorizer_factory():
    yield
    set_authorizer_factory(None)


def test_build_workflow_wraps_steps_between_start_and_done():
    workflow = build_workflow(DEFINITION)

    assert (workflow.name, workflow.description, workflow.target) == ("designed_note", "Store a note", Target.SYSTEM)
    assert [step.name for step in workflow.steps] == ["Start", "Store note", "Set checked_by", "Done"]


@pytest.mark.parametrize(
    ("step_ref", "reason"),
    [
        pytest.param(StepRef(step_id="app.workflows.gone:step"), "no longer exists", id="missing-code-step"),
        pytest.param(StepRef(step_id="designer:unknown"), "unknown helper", id="unknown-helper"),
        pytest.param(
            StepRef(step_id="designer:set_value", config={"key": "?"}), "invalid configuration", id="bad-config"
        ),
    ],
)
def test_unbuildable_step_becomes_a_failing_placeholder(step_ref, reason):
    placeholder = build_step(step_ref)

    assert placeholder.name == f"Unavailable step {step_ref.step_id}"
    with pytest.raises(RuntimeError, match=reason):
        orig(placeholder)()


def test_invalid_workflow_lists_and_fails_when_run():
    workflow = build_invalid_workflow("designed_broken", "its stored definition is invalid")

    assert workflow.name == "designed_broken"
    with pytest.raises(RuntimeError, match="stored definition is invalid"):
        orig(workflow.steps[1])()


def test_default_authorizers_are_the_apps_internal_callbacks():
    workflow = build_workflow(DEFINITION)

    assert workflow.authorize_callback == get_authorizers().authorize_callback
    assert workflow.retry_auth_callback == get_authorizers().retry_auth_callback


def test_authorizer_factory_decides_per_workflow_name():
    names: list[str] = []

    def factory(name: str):
        names.append(name)

        async def only_designed_note(context: AuthContext) -> bool:
            return name == "designed_note"

        return only_designed_note

    set_authorizer_factory(factory)
    workflow = build_workflow(DEFINITION)

    assert names == ["designed_note"]
    assert workflow.retry_auth_callback is workflow.authorize_callback
    assert asyncio.run(workflow.authorize_callback(AuthContext(user=None, workflow=workflow, action="start_workflow")))


def test_set_authorizer_factory_invalidates_cached_workflows(monkeypatch):
    from orchestrator.core.workflow_designer import source

    invalidated: list[str | None] = []
    monkeypatch.setattr(source.designed_workflows, "invalidate", lambda name=None: invalidated.append(name))

    set_authorizer_factory(lambda name: None)

    assert invalidated == [None]
    assert builder._authorizer_factory is not None
