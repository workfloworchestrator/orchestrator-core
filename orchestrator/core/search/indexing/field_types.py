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

from collections import defaultdict
from collections.abc import Iterable
from functools import lru_cache
from itertools import chain
from typing import Any, get_args

from pydantic import BaseModel

from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY, SubscriptionModel
from orchestrator.core.domain.base import DomainModel
from orchestrator.core.domain.lifecycle import lookup_specialized_type
from orchestrator.core.search.core.types import EntityType, FieldType, UIType
from orchestrator.core.search.indexing.schema import iter_model_field_annotations
from orchestrator.core.types import SubscriptionLifecycle, is_list_type


def _model_types(annotation: Any) -> set[type[BaseModel]]:
    """Return Pydantic model types contained in an annotation."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return {annotation}
    return {model_type for arg in get_args(annotation) for model_type in _model_types(arg)}


def _field_annotations(model_type: type[BaseModel]) -> Iterable[tuple[str, Any]]:
    """Yield fields using domain-model classification when available."""
    if issubclass(model_type, DomainModel):
        yield from model_type._non_product_block_fields_.items()
        yield from model_type._product_block_fields_.items()
        yield from (
            (name, computed_field.return_type)
            for name, computed_field in getattr(model_type, "__pydantic_computed_fields__", {}).items()
        )
        return

    yield from iter_model_field_annotations(model_type)


def _collect_field_types(
    model_type: type[BaseModel],
    path: str,
    ancestors: set[type[BaseModel]],
) -> Iterable[tuple[str, FieldType]]:
    """Recursively yield indexed-path/FieldType entries for a model, guarding against recursive references."""
    if model_type in ancestors:
        return

    ancestors = ancestors | {model_type}
    yield from chain.from_iterable(
        _field_type_entries(name, annotation, path, ancestors) for name, annotation in _field_annotations(model_type)
    )


def _field_type_entries(
    name: str,
    annotation: Any,
    path: str,
    ancestors: set[type[BaseModel]],
) -> Iterable[tuple[str, FieldType]]:
    """Return the indexed-path/FieldType entries contributed by a single field."""
    field_path = f"{path}.{name}"
    indexed_path = f"{field_path}.*" if is_list_type(annotation) else field_path
    nested_model_types = _model_types(annotation)
    if not nested_model_types:
        yield indexed_path, FieldType.from_type_hint(annotation)
        return

    yield from chain.from_iterable(
        _collect_field_types(nested_model_type, indexed_path, ancestors) for nested_model_type in nested_model_types
    )


def _specialized_subscription_types(model_type: type[SubscriptionModel]) -> set[type[SubscriptionModel]]:
    """Return a registered subscription model and its lifecycle-specialized variants."""
    return {lookup_specialized_type(model_type, lifecycle) for lifecycle in (None, *SubscriptionLifecycle)}


@lru_cache(maxsize=1)
def _subscription_field_types() -> dict[str, frozenset[FieldType]]:
    """Build searchable subscription field types from registered Pydantic models."""
    field_types: dict[str, set[FieldType]] = defaultdict(set)
    model_types = {
        specialized_type
        for registered_model_type in SUBSCRIPTION_MODEL_REGISTRY.values()
        for specialized_type in _specialized_subscription_types(registered_model_type)
    }
    for path, field_type in chain.from_iterable(
        _collect_field_types(model_type, "subscription", set()) for model_type in model_types
    ):
        field_types[path].add(field_type)
    return {path: frozenset(types) for path, types in field_types.items()}


@lru_cache(maxsize=1)
def _subscription_field_suffix_types() -> dict[str, frozenset[FieldType]]:
    """Build field types indexed by their final path segment."""
    suffix_types: dict[str, set[FieldType]] = defaultdict(set)
    for field_path, field_types in _subscription_field_types().items():
        suffix = field_path.rsplit(".", maxsplit=1)[-1]
        suffix_types[suffix].update(field_types)
    return {suffix: frozenset(types) for suffix, types in suffix_types.items()}


def clear_field_type_cache() -> None:
    """Clear cached subscription field types after changing the model registry."""
    _subscription_field_types.cache_clear()
    _subscription_field_suffix_types.cache_clear()


def resolve_field_types(entity_type: EntityType, path: str) -> frozenset[FieldType]:
    """Return the Pydantic-derived index types for an exact or global field path."""
    if entity_type != EntityType.SUBSCRIPTION:
        return frozenset()

    if "." in path:
        schema_path = ".".join("*" if segment.isdigit() else segment for segment in path.split("."))
        return _subscription_field_types().get(schema_path, frozenset())
    return _subscription_field_suffix_types().get(path, frozenset())


def resolve_field_value_kind(entity_type: EntityType, path: str) -> UIType | None:
    """Return the UI type for a schema-resolved field when it is unambiguous."""
    field_types = resolve_field_types(entity_type, path)
    if field_types == {FieldType.STRING}:
        return UIType.STRING
    if field_types and field_types <= {FieldType.INTEGER, FieldType.FLOAT}:
        return UIType.NUMBER
    return None
