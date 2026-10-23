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

"""The dynamic initial form of a designed workflow.

A designed workflow asks for its input with one form page whose fields are stored in the definition. Field types are
a registry, so an application can add its own pickers with `register_field_type`, e.g. a subscription selector.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, create_model, field_validator

from orchestrator.core.forms import SubmitFormPage
from orchestrator.core.forms.validators import CustomerId
from orchestrator.core.workflow_designer.type_refs import TypeRef
from pydantic_forms.types import FormGenerator, State
from pydantic_forms.validators import Choice, LongText

# The engine puts these in the initial state after the form ran, so a form field with such a name would be ignored.
ENGINE_KEYS: dict[str, TypeRef] = {
    "process_id": TypeRef(kind="uuid"),
    "reporter": TypeRef(kind="str"),
    "workflow_name": TypeRef(kind="str"),
    "workflow_target": TypeRef(kind="str"),
}
RESERVED_FIELD_NAMES = {*ENGINE_KEYS, "state"}
FIELD_NAME_PATTERN = r"^[a-z][a-z0-9_]{0,62}$"


class FieldOptions(BaseModel):
    """Options for the field types that take them; unused options are ignored."""

    choices: list[str] = []
    product_tags: list[str] = []
    statuses: list[str] = []


class FormField(BaseModel):
    name: Annotated[str, Field(pattern=FIELD_NAME_PATTERN)]
    type: str
    title: str = ""
    description: str = ""
    required: bool = True
    default: Any = None
    options: FieldOptions = FieldOptions()

    @field_validator("name")
    @classmethod
    def not_reserved(cls, name: str) -> str:
        if name in RESERVED_FIELD_NAMES:
            raise ValueError(f"'{name}' is set by the workflow engine and cannot be a form field")
        return name


@dataclass(frozen=True)
class FieldType:
    """How a designer field type becomes a pydantic annotation, and what it puts in the state.

    `suggest` decides whether this type can provide a step input (by name and type) that nothing else provides, and
    returns the options to use; the designer then offers to add such a field to the form.
    """

    key: str
    label: str
    annotation: Callable[[FieldOptions], Any]
    state_type: Callable[[FieldOptions], TypeRef]
    options: list[Literal["choices", "product_tags", "statuses"]] = field(default_factory=list)
    suggest: Callable[[str, TypeRef], FieldOptions | None] | None = None


def suggest_kind(kind: str) -> Callable[[str, TypeRef], FieldOptions | None]:
    return lambda _, ref: FieldOptions() if ref.kind == kind else None


def _suggest_customer(name: str, ref: TypeRef) -> FieldOptions | None:
    return FieldOptions() if name == "customer_id" and ref.kind in ("uuid", "str") else None


def _choice_annotation(options: FieldOptions) -> Any:
    if not options.choices:
        return str
    return Choice.__call__("DesignerChoice", {choice: choice for choice in options.choices})


FIELD_TYPES: dict[str, FieldType] = {
    field_type.key: field_type
    for field_type in [
        FieldType("string", "Text", lambda _: str, lambda _: TypeRef(kind="str"), suggest=suggest_kind("str")),
        FieldType("text", "Long text", lambda _: LongText, lambda _: TypeRef(kind="str")),
        FieldType("integer", "Number", lambda _: int, lambda _: TypeRef(kind="int"), suggest=suggest_kind("int")),
        FieldType("boolean", "Yes/no", lambda _: bool, lambda _: TypeRef(kind="bool"), suggest=suggest_kind("bool")),
        FieldType("uuid", "UUID", lambda _: UUID, lambda _: TypeRef(kind="uuid"), suggest=suggest_kind("uuid")),
        FieldType("choice", "Choice", _choice_annotation, lambda _: TypeRef(kind="str"), ["choices"]),
        FieldType(
            "customer", "Customer", lambda _: CustomerId, lambda _: TypeRef(kind="uuid"), suggest=_suggest_customer
        ),
    ]
}


def register_field_type(field_type: FieldType) -> None:
    FIELD_TYPES[field_type.key] = field_type


def suggest_field(name: str, required_type: TypeRef) -> FormField | None:
    """A form field that provides a missing step input, preferring the most recently registered (most specific) type."""
    return next(
        (
            FormField(name=name, type=field_type.key, title=name.replace("_", " ").capitalize(), options=options)
            for field_type in reversed(FIELD_TYPES.values())
            if field_type.suggest and (options := field_type.suggest(name, required_type)) is not None
        ),
        None,
    )


def field_state_type(form_field: FormField) -> TypeRef:
    field_type = FIELD_TYPES.get(form_field.type)
    if field_type is None:
        return TypeRef()
    ref = field_type.state_type(form_field.options)
    return ref.model_copy(update={"optional": not form_field.required and form_field.default is None})


def form_model(fields: list[FormField], title: str) -> type[SubmitFormPage]:
    """Build the pydantic form page for `fields`; raises KeyError for an unknown field type."""

    def definition(form_field: FormField) -> tuple[Any, Any]:
        annotation = FIELD_TYPES[form_field.type].annotation(form_field.options)
        info = Field(title=form_field.title or None, description=form_field.description or None)
        if form_field.required and form_field.default is None:
            return Annotated[annotation, info], ...
        if form_field.default is None:
            return Annotated[annotation | None, info], None
        return Annotated[annotation, info], form_field.default

    model = create_model(  # type: ignore[call-overload]
        "DesignedWorkflowForm",
        __base__=SubmitFormPage,
        **{form_field.name: definition(form_field) for form_field in fields},
    )
    model.model_config["title"] = title
    return model


def build_initial_form(fields: list[FormField], title: str) -> Callable[[State], FormGenerator]:
    """A form generator for `make_workflow`; the page is built lazily so it can use the DB-backed validators."""

    def initial_input_form(state: State) -> FormGenerator:
        user_input = yield form_model(fields, title)
        return user_input.model_dump()

    return initial_input_form
