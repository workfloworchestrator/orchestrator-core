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

"""A small type vocabulary for checking whether one step's state can feed the next.

Step parameters carry real annotations, but the workflow state is JSON between steps, so richer types (UUID, wrapped
ids, enums, domain models) collapse to a handful of wire kinds. Comparing those kinds is what the designer can check.
"""

import types
from enum import Enum
from typing import Annotated, Any, Literal, Union, get_args, get_origin
from uuid import UUID

import structlog
from pydantic import BaseModel, Field

from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY, SubscriptionModel
from orchestrator.core.domain.lifecycle import lookup_specialized_type
from orchestrator.core.types import SubscriptionLifecycle

logger = structlog.get_logger(__name__)

TypeKind = Literal["str", "int", "float", "bool", "uuid", "list", "dict", "subscription", "any"]
Severity = Literal["ok", "warning", "error"]

# `UUIDstr` is a plain alias of `str`, so the annotation object cannot tell it apart; its source text can.
UUID_ANNOTATION_NAMES = {"UUIDstr", "UUID"}
UUID_PARAM_NAMES = {"subscription_id", "process_id"}

_PRIMITIVES: dict[type, TypeKind] = {str: "str", int: "int", float: "float", bool: "bool", UUID: "uuid"}
_COLLECTIONS: dict[Any, TypeKind] = {list: "list", set: "list", tuple: "list", frozenset: "list", dict: "dict"}


class TypeRef(BaseModel):
    kind: TypeKind = "any"
    optional: bool = False
    model: str | None = Field(default=None, description="Subscription model class, only for kind 'subscription'")
    product_tags: list[str] = Field(
        default_factory=list, description="Product tags the subscription can have; empty means unrestricted"
    )
    statuses: list[str] = Field(
        default_factory=list, description="Lifecycle statuses the subscription can have; empty means unrestricted"
    )

    @property
    def label(self) -> str:
        base = self.model if self.kind == "subscription" and self.model else self.kind
        return f"{base} | None" if self.optional else base


ANY = TypeRef()


def _strip_optional(annotation: Any) -> tuple[Any, bool]:
    if get_origin(annotation) in (Union, types.UnionType):
        args = get_args(annotation)
        non_none = [arg for arg in args if arg is not type(None)]
        if len(non_none) < len(args):
            return (non_none[0] if len(non_none) == 1 else Union[tuple(non_none)]), True  # noqa: UP007
    return annotation, False


def _wrapped_value_kind(annotation: type) -> TypeKind | None:
    """Kind of the primitive a wrapped id (e.g. ``ImsId``) unwraps to when a step returns it into the state."""
    # The value type is a generic argument somewhere up the MRO: `class IntId(Id[EntityT, int])`.
    return next(
        (
            _PRIMITIVES[arg]
            for base in annotation.__mro__
            for orig_base in getattr(base, "__orig_bases__", ())
            for arg in get_args(orig_base)
            if isinstance(arg, type) and arg in _PRIMITIVES
        ),
        None,
    )


def subscription_model_ref(model: type[SubscriptionModel], product_tags_by_name: dict[str, str]) -> TypeRef:
    """TypeRef for a domain model, with the products and lifecycles `from_subscription` will accept for it."""
    if model is SubscriptionModel or model.__base_type__ is None:
        return TypeRef(kind="subscription")

    base_type = model.__base_type__
    product_names = [name for name, klass in SUBSCRIPTION_MODEL_REGISTRY.items() if klass.__base_type__ is base_type]
    product_tags = sorted({product_tags_by_name[name] for name in product_names if name in product_tags_by_name})
    # `from_subscription` accepts any lifecycle whose model is a base class of `model`, but the stricter model then
    # fails to validate a less complete subscription; so prefer the lifecycles that map to exactly this model.
    specialized = {status: lookup_specialized_type(model, status) for status in SubscriptionLifecycle}
    exact = [str(status) for status, klass in specialized.items() if klass is model]
    accepted = [str(status) for status, klass in specialized.items() if issubclass(model, klass)]
    return TypeRef(kind="subscription", model=model.__name__, product_tags=product_tags, statuses=exact or accepted)


def type_ref_for(
    annotation: Any,
    annotation_src: str | None = None,
    param_name: str | None = None,
    product_tags_by_name: dict[str, str] | None = None,
) -> TypeRef:
    """Map a Python annotation to the kind of value it takes (or leaves) in the JSON workflow state."""
    if get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    annotation, optional = _strip_optional(annotation)
    if get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]

    ref = _type_ref(annotation, annotation_src, param_name, product_tags_by_name or {})
    return ref.model_copy(update={"optional": optional or ref.optional})


def _type_ref(
    annotation: Any, annotation_src: str | None, param_name: str | None, product_tags_by_name: dict[str, str]
) -> TypeRef:
    origin = get_origin(annotation)

    if annotation is str and (
        (annotation_src and any(name in annotation_src for name in UUID_ANNOTATION_NAMES))
        or param_name in UUID_PARAM_NAMES
    ):
        return TypeRef(kind="uuid")
    if origin is Literal:
        kinds = {_PRIMITIVES.get(type(arg)) for arg in get_args(annotation)}
        kind = kinds.pop() if len(kinds) == 1 else None
        return TypeRef(kind=kind or "any")
    if origin in (Union, types.UnionType):
        return ANY
    if origin is not None:
        return TypeRef(kind=_COLLECTIONS.get(origin, "list" if hasattr(origin, "__iter__") else "any"))
    if not isinstance(annotation, type):
        return ANY
    if issubclass(annotation, SubscriptionModel):
        return subscription_model_ref(annotation, product_tags_by_name)
    return _class_ref(annotation)


def _class_ref(annotation: type) -> TypeRef:
    if issubclass(annotation, Enum):
        mixed_in = next((base for base in annotation.__mro__ if base in _PRIMITIVES), None)
        return TypeRef(kind=_PRIMITIVES[mixed_in] if mixed_in else "any")
    if annotation in _PRIMITIVES:
        return TypeRef(kind=_PRIMITIVES[annotation])
    if annotation in _COLLECTIONS:
        return TypeRef(kind=_COLLECTIONS[annotation])
    if callable(getattr(annotation, "unwrap", None)) and (kind := _wrapped_value_kind(annotation)):
        return TypeRef(kind=kind)
    # Subclass checks after the exact matches: `bool` is an `int` and wrapped ids are dataclasses.
    subclass_kinds: list[tuple[type | tuple[type, ...], TypeKind]] = [
        ((BaseModel, dict), "dict"),
        ((list, tuple, set), "list"),
        (str, "str"),
        (int, "int"),
    ]
    return next((TypeRef(kind=kind) for base, kind in subclass_kinds if issubclass(annotation, base)), ANY)


class Compatibility(BaseModel):
    severity: Severity
    message: str = ""


OK = Compatibility(severity="ok")


def _check_subscription(provided: TypeRef, required: TypeRef) -> Compatibility:
    if required.model is None:
        return OK
    if not required.product_tags:
        return Compatibility(severity="warning", message=f"cannot verify that the subscription is a {required.model}")
    if not provided.product_tags:
        return Compatibility(
            severity="error",
            message=f"any product is allowed here, but a {required.model} is needed "
            f"(restrict to product tags {', '.join(required.product_tags)})",
        )
    if extra_tags := sorted(set(provided.product_tags) - set(required.product_tags)):
        return Compatibility(
            severity="error", message=f"product tags {', '.join(extra_tags)} are not a {required.model}"
        )
    # A picker without explicit statuses only offers active subscriptions.
    provided_statuses = provided.statuses or [str(SubscriptionLifecycle.ACTIVE)]
    if required.statuses and (extra_statuses := sorted(set(provided_statuses) - set(required.statuses))):
        return Compatibility(
            severity="error",
            message=f"{required.model} cannot be loaded for subscriptions that are {', '.join(extra_statuses)}",
        )
    return OK


def check(provided: TypeRef, required: TypeRef) -> Compatibility:
    """Decide whether a state value of type `provided` can be injected into a parameter of type `required`."""
    if required.kind == "any":
        return OK
    if provided.kind == "any":
        return Compatibility(severity="warning", message=f"type is unknown, expected {required.label}")

    result = _check_kinds(provided, required)
    if result.severity == "ok" and provided.optional and not required.optional:
        return Compatibility(severity="warning", message=f"may be empty, but {required.label} is required")
    return result


def _check_kinds(provided: TypeRef, required: TypeRef) -> Compatibility:
    pair = (provided.kind, required.kind)
    if provided.kind == required.kind:
        return _check_subscription(provided, required) if provided.kind == "subscription" else OK
    if pair in {("int", "float"), ("uuid", "str"), ("subscription", "uuid"), ("subscription", "str")}:
        return OK
    # Steps often hand ids on as `str(...)`; those are plausibly, but not provably, the id that is needed.
    if pair in {("str", "uuid"), ("uuid", "subscription"), ("str", "subscription"), ("dict", "subscription")}:
        return Compatibility(severity="warning", message=f"{provided.label} is not guaranteed to be a {required.label}")
    return Compatibility(severity="error", message=f"expected {required.label}, got {provided.label}")
