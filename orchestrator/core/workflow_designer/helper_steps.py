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

"""Small configurable steps that glue existing steps together in a designed workflow.

Code steps have a fixed interface. Helpers take a config from the definition instead, and their inputs and outputs
depend on it: `log_message` reads whatever keys its template mentions. Each helper builds a real `@step` (or
`@inputstep`) at workflow build time, so the engine runs them like any other step.
"""

import string
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ValidationInfo, create_model, field_validator

from orchestrator.core.config.assignee import Assignee
from orchestrator.core.forms import SubmitFormPage
from orchestrator.core.services import subscriptions
from orchestrator.core.workflow import Step, inputstep, step
from orchestrator.core.workflow_designer.discovery import StepInfo, StepInput
from orchestrator.core.workflow_designer.forms import FIELD_NAME_PATTERN, RESERVED_FIELD_NAMES
from orchestrator.core.workflow_designer.inference import StateKey
from orchestrator.core.workflow_designer.type_refs import TypeRef
from pydantic_forms.types import FormGenerator, State
from pydantic_forms.validators import Accept, callout

HELPER_PREFIX = "designer:"
DESIGNER_LOG_KEY = "designer_log"
StateKeyName = Annotated[str, Field(pattern=FIELD_NAME_PATTERN)]


def _not_reserved(key: str) -> str:
    if key in RESERVED_FIELD_NAMES:
        raise ValueError(f"'{key}' is set by the workflow engine")
    return key


class SetValueConfig(BaseModel):
    key: StateKeyName
    type: Literal["str", "int", "float", "bool"] = "str"
    value: str | int | float | bool = ""

    _check_key = field_validator("key")(_not_reserved)

    @field_validator("value")
    @classmethod
    def value_matches_type(cls, value: Any, info: ValidationInfo) -> Any:
        value_type = {"str": str, "int": int, "float": float, "bool": bool}[info.data.get("type", "str")]
        # The GUI edits every value as text, and `bool("false")` is True.
        if value_type is bool and isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        try:
            return value_type(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"'{value}' is not a valid {value_type.__name__}") from exc


class LogMessageConfig(BaseModel):
    template: Annotated[str, Field(min_length=1, description="Text to log; {key} is replaced by that state value")]

    @field_validator("template")
    @classmethod
    def valid_template(cls, template: str) -> str:
        placeholders(template)
        return template


class LoadSubscriptionInfoConfig(BaseModel):
    source_key: StateKeyName = "subscription_id"
    prefix: Annotated[str, Field(pattern=r"^([a-z][a-z0-9_]*_)?$")] = "subscription_"


class ConfirmConfig(BaseModel):
    message: Annotated[str, Field(min_length=1)] = "Please confirm to continue."


def placeholders(template: str) -> list[str]:
    """State keys a log template refers to, e.g. `{customer_name}`; raises ValueError for malformed templates."""
    try:
        fields = [field_name for _, field_name, _, _ in string.Formatter().parse(template) if field_name is not None]
    except ValueError as exc:
        raise ValueError(f"invalid template: {exc}") from exc
    if invalid := [name for name in fields if not name.isidentifier()]:
        raise ValueError(f"placeholders must be plain state keys, got {', '.join(map(repr, invalid))}")
    return list(dict.fromkeys(fields))


@dataclass(frozen=True)
class HelperSpec:
    id: str
    name: str
    description: str
    config_model: type[BaseModel]
    inputs: Callable[[Any], list[tuple[str, TypeRef]]]
    outputs: Callable[[Any], list[StateKey]]
    build: Callable[[Any], Step]
    kind: Literal["step", "inputstep"] = "step"
    # What the palette assumes when checking where the helper fits, before the user configured it.
    default_config: dict[str, Any] = field(default_factory=dict)


def _build_set_value(config: SetValueConfig) -> Step:
    @step(f"Set {config.key}")
    def set_value() -> State:
        return {config.key: config.value}

    return set_value


def _build_log_message(config: LogMessageConfig) -> Step:
    keys = placeholders(config.template)

    # The template's keys are only known at build time, so the step reads them from the whole state.
    @step("Log message")
    def log_message(state: State) -> State:
        message = config.template.format_map({key: state.get(key) for key in keys})
        return {DESIGNER_LOG_KEY: [*state.get(DESIGNER_LOG_KEY, []), message]}

    return log_message


SUBSCRIPTION_INFO_FIELDS: dict[str, TypeRef] = {
    "description": TypeRef(kind="str"),
    "status": TypeRef(kind="str"),
    "insync": TypeRef(kind="bool"),
    "product_name": TypeRef(kind="str"),
    "product_tag": TypeRef(kind="str"),
    "customer_id": TypeRef(kind="str"),
}


def _build_load_subscription_info(config: LoadSubscriptionInfoConfig) -> Step:
    @step("Load subscription info")
    def load_subscription_info(state: State) -> State:
        subscription = subscriptions.get_subscription(state[config.source_key])
        values = {
            "description": subscription.description,
            "status": subscription.status,
            "insync": subscription.insync,
            "product_name": subscription.product.name,
            "product_tag": subscription.product.tag,
            "customer_id": subscription.customer_id,
        }
        return {f"{config.prefix}{key}": value for key, value in values.items()}

    return load_subscription_info


def _build_confirm(config: ConfirmConfig) -> Step:
    @inputstep("Confirm", assignee=Assignee.SYSTEM)
    def confirm() -> FormGenerator:
        page = create_model(
            "DesignerConfirmForm",
            __base__=SubmitFormPage,
            designer_confirmation=(callout(header="Confirm", message=config.message), None),
            accept_designer_confirmation=(Accept, ...),
        )
        page.model_config["title"] = "Confirm"
        yield page
        return {"confirmed": True}

    return confirm


HELPERS: dict[str, HelperSpec] = {
    spec.id: spec
    for spec in [
        HelperSpec(
            id=f"{HELPER_PREFIX}set_value",
            name="Set value",
            description="Put a fixed value in the state, e.g. to feed a step input that no form field provides.",
            config_model=SetValueConfig,
            inputs=lambda _: [],
            outputs=lambda config: [StateKey(key=config.key, type=TypeRef(kind=config.type))],
            build=_build_set_value,
            default_config={"key": "value"},
        ),
        HelperSpec(
            id=f"{HELPER_PREFIX}log_message",
            name="Log message",
            description="Append a message built from state values to `designer_log`, e.g. 'Checked {subscription_id}'.",
            config_model=LogMessageConfig,
            inputs=lambda config: [(key, TypeRef()) for key in placeholders(config.template)],
            outputs=lambda _: [StateKey(key=DESIGNER_LOG_KEY, type=TypeRef(kind="list"))],
            build=_build_log_message,
            default_config={"template": "Done"},
        ),
        HelperSpec(
            id=f"{HELPER_PREFIX}load_subscription_info",
            name="Load subscription info",
            description="Read description, status, product and customer of a subscription into the state.",
            config_model=LoadSubscriptionInfoConfig,
            inputs=lambda config: [(config.source_key, TypeRef(kind="uuid"))],
            outputs=lambda config: [
                StateKey(key=f"{config.prefix}{key}", type=ref) for key, ref in SUBSCRIPTION_INFO_FIELDS.items()
            ],
            build=_build_load_subscription_info,
        ),
        HelperSpec(
            id=f"{HELPER_PREFIX}confirm",
            name="Ask for confirmation",
            description="Pause the workflow until a user confirms, e.g. before a step that changes something.",
            config_model=ConfirmConfig,
            inputs=lambda _: [],
            outputs=lambda _: [StateKey(key="confirmed", type=TypeRef(kind="bool"))],
            build=_build_confirm,
            kind="inputstep",
        ),
    ]
}


def is_helper(step_id: str) -> bool:
    return step_id.startswith(HELPER_PREFIX)


def default_config(step_id: str) -> dict[str, Any]:
    spec = HELPERS.get(step_id)
    return spec.default_config if spec else {}


def helper_step_infos() -> dict[str, StepInfo]:
    """The helpers described like discovered steps, with the interface of their default config."""

    def info(spec: HelperSpec) -> StepInfo:
        config = spec.config_model.model_validate(spec.default_config)
        return StepInfo(
            id=spec.id,
            name=spec.name,
            function=spec.id.removeprefix(HELPER_PREFIX),
            module="designer",
            category="designer",
            description=spec.description,
            kind="helper",
            inputs=[
                StepInput(name=name, type=ref, annotation=ref.label, required=True) for name, ref in spec.inputs(config)
            ],
            outputs=spec.outputs(config),
            config_schema=spec.config_model.model_json_schema(),
            config_defaults=spec.default_config,
            pauses=spec.kind == "inputstep",
        )

    return {spec.id: info(spec) for spec in HELPERS.values()}
