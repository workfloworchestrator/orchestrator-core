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

"""The workflow type must keep listing when a workflows row can no longer be resolved to a workflow."""

import asyncio
from types import SimpleNamespace
from unittest import mock

import pytest

import orchestrator.core.graphql.schemas.workflow as workflow_schema
from orchestrator.core.config.assignee import Assignee
from orchestrator.core.targets import Target
from orchestrator.core.workflow import StepList, make_workflow


def _resolver(name: str):
    definition = workflow_schema.Workflow.__strawberry_definition__  # type: ignore[attr-defined]
    field = next(f for f in definition.fields if f.name == name)
    return field.base_resolver.wrapped_func


def _info():
    async def no_user():
        return None

    return SimpleNamespace(context=SimpleNamespace(get_current_user=no_user()))


def _row(name: str):
    return SimpleNamespace(name=name, _original_model=SimpleNamespace(name=name))


def test_steps_of_unresolvable_workflow_is_empty():
    with mock.patch.object(workflow_schema, "get_workflow", return_value=None):
        assert _resolver("steps")(_row("gone")) == []


def test_steps_of_resolvable_workflow():
    workflow = SimpleNamespace(steps=[SimpleNamespace(name="Start", assignee=Assignee.SYSTEM)])
    with mock.patch.object(workflow_schema, "get_workflow", return_value=workflow):
        steps = _resolver("steps")(_row("present"))

    assert [(step.name, step.assignee) for step in steps] == [("Start", Assignee.SYSTEM)]


def test_unresolvable_workflow_is_not_allowed():
    with mock.patch.object(workflow_schema, "get_workflow", return_value=None):
        assert asyncio.run(_resolver("is_allowed")(_row("gone"), _info())) is False


@pytest.mark.parametrize("allowed", [pytest.param(True, id="allowed"), pytest.param(False, id="denied")])
def test_resolvable_workflow_uses_its_authorize_callback(allowed):
    async def authorize(_context):
        return allowed

    workflow = make_workflow(lambda: None, "", None, Target.SYSTEM, StepList(), authorize_callback=authorize)
    with mock.patch.object(workflow_schema, "get_workflow", return_value=workflow):
        assert asyncio.run(_resolver("is_allowed")(_row("present"), _info())) is allowed
