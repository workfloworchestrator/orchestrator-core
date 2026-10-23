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

"""Designed workflow definitions and the check that every step gets the state it needs.

Validation simulates the state through the step list: the engine keys and form fields first, then each step's
guaranteed outputs. A step whose required input is not in the state at that point, or has an incompatible type,
makes the definition invalid, so it cannot be saved.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from orchestrator.core.settings import app_settings
from orchestrator.core.workflow_designer.discovery import StepInfo
from orchestrator.core.workflow_designer.forms import (
    ENGINE_KEYS,
    FIELD_TYPES,
    FormField,
    field_state_type,
    suggest_field,
)
from orchestrator.core.workflow_designer.helper_steps import HELPERS, default_config, is_helper
from orchestrator.core.workflow_designer.inference import StateKey
from orchestrator.core.workflow_designer.type_refs import Severity, TypeRef, check

NAME_PATTERN = r"^[a-z][a-z0-9_]{2,63}$"


class StepRef(BaseModel):
    step_id: str
    config: dict[str, Any] = {}


class WorkflowDefinition(BaseModel):
    name: Annotated[str, Field(pattern=NAME_PATTERN)]
    description: Annotated[str, Field(min_length=1, max_length=2000)]
    form_fields: list[FormField] = []
    steps: list[StepRef] = []

    @field_validator("name")
    @classmethod
    def has_prefix(cls, name: str) -> str:
        prefix = app_settings.WORKFLOW_DESIGNER_NAME_PREFIX
        if not name.startswith(prefix):
            raise ValueError(f"designed workflow names start with '{prefix}'")
        return name

    @model_validator(mode="after")
    def unique_field_names(self) -> "WorkflowDefinition":
        names = [form_field.name for form_field in self.form_fields]
        if duplicates := sorted({name for name in names if names.count(name) > 1}):
            raise ValueError(f"duplicate form fields: {', '.join(duplicates)}")
        return self


class Issue(BaseModel):
    severity: Literal["warning", "error"]
    message: str
    position: int | None = Field(default=None, description="Step index; None for the definition or the form")
    step_id: str | None = None
    input: str | None = None


class PaletteStatus(BaseModel):
    status: Literal["ok", "warning", "needs_form", "incompatible", "unusable"]
    message: str = ""
    suggested_fields: list[FormField] = []


class ValidationResult(BaseModel):
    valid: bool
    issues: list[Issue]
    available: list[list[StateKey]] = Field(
        description="State keys available before each step; the last entry is the state after the final step"
    )
    palette: dict[str, PaletteStatus] | None = None


class StepInterface(BaseModel):
    inputs: list[tuple[str, TypeRef, bool]]
    outputs: list[StateKey]
    usable: bool = True
    reason: str | None = None


def step_interface(step_ref: StepRef, steps: dict[str, StepInfo]) -> StepInterface:
    """Inputs as (name, type, required) and outputs of the step a reference points to, given its config."""
    if is_helper(step_ref.step_id):
        spec = HELPERS.get(step_ref.step_id)
        if spec is None:
            return StepInterface(inputs=[], outputs=[], usable=False, reason="unknown helper")
        try:
            config = spec.config_model.model_validate(step_ref.config)
        except ValidationError as exc:
            errors = "; ".join(f"{'.'.join(map(str, error['loc']))}: {error['msg']}" for error in exc.errors())
            return StepInterface(inputs=[], outputs=[], usable=False, reason=f"invalid configuration: {errors}")
        return StepInterface(
            inputs=[(name, ref, True) for name, ref in spec.inputs(config)], outputs=spec.outputs(config)
        )

    info = steps.get(step_ref.step_id)
    if info is None:
        return StepInterface(inputs=[], outputs=[], usable=False, reason="step does not exist (anymore)")
    return StepInterface(
        inputs=[(step_input.name, step_input.type, step_input.required) for step_input in info.inputs],
        outputs=[output for output in info.outputs if output.guaranteed],
        usable=info.usable,
        reason=info.unusable_reason,
    )


def initial_state(form_fields: list[FormField]) -> dict[str, TypeRef]:
    return {
        **{form_field.name: field_state_type(form_field) for form_field in form_fields},
        **ENGINE_KEYS,  # Engine keys win: `create_process` merges them over the form output.
    }


def check_inputs(interface: StepInterface, available: dict[str, TypeRef]) -> list[tuple[str, Severity, str]]:
    """Problems with feeding `interface` from the `available` state, as (input, severity, message)."""
    problems: list[tuple[str, Severity, str]] = []
    for name, required_type, required in interface.inputs:
        if name not in available:
            if required:
                problems.append((name, "error", f"needs '{name}' ({required_type.label}), which is not in the state"))
            continue
        result = check(available[name], required_type)
        if result.severity != "ok":
            problems.append((name, result.severity, f"'{name}': {result.message}"))
    return problems


def _apply_outputs(available: dict[str, TypeRef], outputs: list[StateKey]) -> dict[str, TypeRef]:
    return {**available, **{output.key: output.type for output in outputs}}


def _as_keys(available: dict[str, TypeRef]) -> list[StateKey]:
    return [StateKey(key=key, type=ref) for key, ref in available.items()]


def palette_status(step_ref: StepRef, available: dict[str, TypeRef], steps: dict[str, StepInfo]) -> PaletteStatus:
    """Whether a step, with its default config, can be inserted where `available` is the state."""
    interface = step_interface(step_ref, steps)
    if not interface.usable:
        return PaletteStatus(status="unusable", message=interface.reason or "")

    problems = check_inputs(interface, available)
    errors = [(name, message) for name, severity, message in problems if severity == "error"]
    if not errors:
        warnings = [message for _, severity, message in problems if severity == "warning"]
        return PaletteStatus(status="warning" if warnings else "ok", message="; ".join(warnings))

    # Missing inputs can be asked for in the initial form; wrong types cannot be fixed that way.
    missing = [name for name, _ in errors if name not in available]
    types = {name: ref for name, ref, _ in interface.inputs}
    suggestions = [suggest_field(name, types[name]) for name in missing]
    if len(missing) == len(errors) and all(suggestions):
        return PaletteStatus(
            status="needs_form",
            message=f"adds form field(s) {', '.join(missing)}",
            suggested_fields=[suggestion for suggestion in suggestions if suggestion],
        )
    return PaletteStatus(status="incompatible", message="; ".join(message for _, message in errors))


def validate_definition(
    definition: WorkflowDefinition, steps: dict[str, StepInfo], insert_at: int | None = None
) -> ValidationResult:
    """Check the step chain; with `insert_at`, also report which palette steps fit at that position."""
    issues = [
        Issue(severity="error", message=f"form field '{form_field.name}' has unknown type '{form_field.type}'")
        for form_field in definition.form_fields
        if form_field.type not in FIELD_TYPES
    ]
    if not definition.steps:
        issues.append(Issue(severity="error", message="a workflow needs at least one step"))

    available = initial_state(definition.form_fields)
    states = [available]
    # A loop because each step's check reads the state that the previous steps built up.
    for position, step_ref in enumerate(definition.steps):
        interface = step_interface(step_ref, steps)
        if not interface.usable:
            issues.append(
                Issue(
                    severity="error",
                    message=interface.reason or "unusable",
                    position=position,
                    step_id=step_ref.step_id,
                )
            )
        issues.extend(
            Issue(severity=severity, message=message, position=position, step_id=step_ref.step_id, input=name)
            for name, severity, message in check_inputs(interface, available)
            if severity != "ok"
        )
        available = _apply_outputs(available, interface.outputs)
        states.append(available)

    palette = None
    if insert_at is not None:
        before = states[max(0, min(insert_at, len(states) - 1))]
        palette = {
            step_id: palette_status(StepRef(step_id=step_id, config=default_config(step_id)), before, steps)
            for step_id in [*HELPERS, *steps]
        }

    return ValidationResult(
        valid=not any(issue.severity == "error" for issue in issues),
        issues=issues,
        available=[_as_keys(state) for state in states],
        palette=palette,
    )
