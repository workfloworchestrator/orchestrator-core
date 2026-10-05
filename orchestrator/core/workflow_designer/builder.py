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

"""Turn a stored definition into a `Workflow` the engine can run."""

from collections.abc import Callable
from typing import NoReturn

from pydantic import ValidationError

from orchestrator.core.settings import get_authorizers
from orchestrator.core.targets import Target
from orchestrator.core.utils.auth import Authorizer
from orchestrator.core.workflow import Step, StepList, Workflow, done, init, make_workflow, step
from orchestrator.core.workflow_designer.definition import StepRef, WorkflowDefinition
from orchestrator.core.workflow_designer.discovery import resolve_step
from orchestrator.core.workflow_designer.forms import build_initial_form
from orchestrator.core.workflow_designer.helper_steps import HELPERS, is_helper

AuthorizerFactory = Callable[[str], Authorizer]
_authorizer_factory: AuthorizerFactory | None = None


def set_authorizer_factory(factory: AuthorizerFactory | None) -> None:
    """Let the application decide who may start a designed workflow, given its name.

    Without a factory, designed workflows use the app's internal authorize and retry callbacks, like core's own tasks.
    """
    from orchestrator.core.workflow_designer.source import designed_workflows

    global _authorizer_factory
    _authorizer_factory = factory
    designed_workflows.invalidate()


def _placeholder_step(name: str, reason: str) -> Step:
    """Stands in for a step that cannot be built, so the workflow still lists and fails clearly when run."""

    @step(f"Unavailable step {name}")
    def unavailable() -> NoReturn:
        raise RuntimeError(f"Step {name} cannot be run: {reason}")

    return unavailable


def build_step(step_ref: StepRef) -> Step:
    if is_helper(step_ref.step_id):
        if (spec := HELPERS.get(step_ref.step_id)) is None:
            return _placeholder_step(step_ref.step_id, "unknown helper")
        try:
            return spec.build(spec.config_model.model_validate(step_ref.config))
        except ValidationError as exc:
            return _placeholder_step(step_ref.step_id, f"invalid configuration: {exc}")
    code_step = resolve_step(step_ref.step_id)
    return (
        code_step if code_step is not None else _placeholder_step(step_ref.step_id, "it no longer exists in the code")
    )


def _make(name: str, description: str, definition: WorkflowDefinition | None, steps: StepList) -> Workflow:
    def designed_workflow() -> NoReturn:
        raise AssertionError("A designed workflow is built by the workflow designer, not called")

    designed_workflow.__name__ = name
    designed_workflow.__qualname__ = name
    designed_workflow.__doc__ = description
    if _authorizer_factory:
        authorize_callback = retry_auth_callback = _authorizer_factory(name)
    else:
        authorize_callback = get_authorizers().authorize_callback
        retry_auth_callback = get_authorizers().retry_auth_callback
    workflow = make_workflow(
        designed_workflow,
        description,
        build_initial_form(definition.form_fields, description) if definition else None,
        Target.SYSTEM,
        init >> steps >> done,
        authorize_callback=authorize_callback,
        retry_auth_callback=retry_auth_callback,
    )
    workflow.name = name
    return workflow


def build_workflow(definition: WorkflowDefinition) -> Workflow:
    """Build the workflow; steps that cannot be built are replaced by steps that fail when run."""
    return _make(
        definition.name,
        definition.description,
        definition,
        StepList([build_step(step_ref) for step_ref in definition.steps]),
    )


def build_invalid_workflow(name: str, reason: str) -> Workflow:
    """A workflow for a stored definition that no longer parses: it still lists, and fails clearly when run."""
    return _make(name, f"Invalid designed workflow {name}", None, StepList([_placeholder_step(name, reason)]))
