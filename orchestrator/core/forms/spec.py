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

"""A form page as data for an agent: one ``FormField`` per field of the page's model.

The browser gets a page as the JSON schema pydantic-forms renders for it: ``$ref`` indirection, widget
hints and ``format`` markers a program has to undo before it knows what a field takes. This reads the
model class instead, the lossless source, and says per field what a caller needs to fill it: the kind
of value, whether it is required, the options it is limited to with their labels, the bounds of a
list, the fields of a nested model, and whether the field is only shown (``display_only``) or shown
and fixed (``read_only``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any, Literal, cast, get_args, get_origin
from uuid import UUID

from more_itertools import first
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined, to_jsonable_python

from orchestrator.core.schemas.mcp_tools import FormField, FormFieldKind, FormFieldOption
from orchestrator.core.types import filter_nonetype, is_optional_type, yield_max_length, yield_min_length
from pydantic_forms.validators import Accept, AcceptValues
from pydantic_forms.validators.constants import EXTRA_PROPERTIES


def form_fields(model: type[BaseModel]) -> list[FormField]:
    """The fields of a page model as data, in the form's order."""
    return [form_field(name, info) for name, info in model.model_fields.items()]


def form_field(name: str, info: FieldInfo) -> FormField:
    """One field of a page: what its model declares, read without rendering a schema."""
    extra = _schema_extra(info.json_schema_extra)
    widgets = next((w for w in (extra.get(EXTRA_PROPERTIES), extra.get("uniforms")) if isinstance(w, Mapping)), {})
    annotation, nullable = _unwrap_optional(_strip_annotated(info.annotation))
    shape = _shape(annotation)
    return FormField(
        name=name,
        title=info.title or name.title().replace("_", " "),  # pydantic's own humanisation of a name
        description=info.description,
        kind=shape.kind,
        format=extra.get("format") or shape.format,
        required=info.is_required(),
        default=_default(info),
        nullable=nullable,
        options=shape.options,
        item=shape.item,
        min_items=first(yield_min_length(info.metadata), None) if shape.kind == "list" else None,
        max_items=first(yield_max_length(info.metadata), None) if shape.kind == "list" else None,
        unique_items=extra.get("uniqueItems") is True,
        fields=shape.fields,
        read_only=bool(widgets.get("disabled")),
        display_only=bool(info.frozen),
        data=_json(shape.data if shape.data is not None else widgets.get("data")),
    )


@dataclass(frozen=True)
class _Shape:
    """What a type takes: its kind and, where the type limits or structures the value, the options, item or fields."""

    kind: FormFieldKind
    format: str | None = None
    options: list[FormFieldOption] | None = None
    item: FormField | None = None
    fields: list[FormField] | None = None
    data: Any = None


def _shape(annotation: Any) -> _Shape:
    origin = get_origin(annotation)
    if origin is Literal:
        values = get_args(annotation)
        kind = _scalar_kind(type(values[0])) if values else "any"
        return _Shape(kind, options=[_option(value, str(value)) for value in values])
    if origin in (list, set, frozenset, tuple):
        item_type = next(iter(get_args(annotation)), Any)
        return _Shape("list", item=_item(item_type))
    if origin is dict or annotation is dict:
        return _Shape("object")
    if not isinstance(annotation, type):
        return _Shape("any")
    if issubclass(annotation, Accept):  # before str: Accept is one
        accepted = AcceptValues.ACCEPTED.value
        return _Shape("string", format="accept", options=[_option(accepted, accepted)], data=annotation.data)
    if issubclass(annotation, Enum):  # before str: a Choice is one
        members = list(annotation.__members__.values())
        kind = _scalar_kind(type(members[0].value)) if members else "string"
        return _Shape(kind, options=[_option(m.value, str(getattr(m, "label", None) or m.value)) for m in members])
    if issubclass(annotation, BaseModel) and annotation.model_fields:
        return _Shape("object", fields=form_fields(annotation))
    if issubclass(annotation, BaseModel):  # a display value (markdown, callout, summary): nothing to submit
        return _Shape("any", data=getattr(annotation, "data", None))
    return _Shape(_scalar_kind(annotation))


def _scalar_kind(type_: type) -> FormFieldKind:
    if issubclass(type_, bool):  # before int: bool is one
        return "boolean"
    if issubclass(type_, int):
        return "integer"
    if issubclass(type_, float):
        return "number"
    if issubclass(type_, (str, UUID, datetime, date)):
        return "string"
    return "any"


def _item(annotation: Any) -> FormField:
    """A list's items as a field of their own: the type's shape, with no name, default or requirement."""
    return form_field("", FieldInfo.from_annotation(annotation)).model_copy(update={"required": False})


def _option(value: Any, label: str) -> FormFieldOption:
    return FormFieldOption(value=_json(value), label=label)


def _default(info: FieldInfo) -> Any:
    """The default as JSON; a factory is evaluated when it takes no data, as the form's own schema does."""
    if info.default is not PydanticUndefined:
        return _json(info.default)
    if info.default_factory is not None and not info.default_factory_takes_validated_data:
        try:
            return _json(cast(Callable[[], Any], info.default_factory)())
        except Exception:  # noqa: BLE001  # a factory that needs more than the form has must not break the page
            return None
    return None


def _schema_extra(extra: Any) -> dict[str, Any]:
    """A field's ``json_schema_extra`` as the dict it renders: given, or built by its callable (display fields)."""
    if isinstance(extra, Mapping):
        return dict(extra)
    if callable(extra):
        built: dict[str, Any] = {}
        cast(Callable[[dict[str, Any]], None], extra)(built)
        return built
    return {}


def _strip_annotated(annotation: Any) -> Any:
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    """The type without its ``None``, and whether it allowed one; a union of several types stays as it is."""
    if not is_optional_type(annotation):
        return annotation, False
    variants = [_strip_annotated(arg) for arg in filter_nonetype(get_args(annotation))]
    return (variants[0] if len(variants) == 1 else annotation), True


def _json(value: Any) -> Any:
    return to_jsonable_python(value, fallback=str)
