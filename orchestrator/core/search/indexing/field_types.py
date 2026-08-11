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
from functools import lru_cache
from typing import Any, get_args, get_origin

from pydantic import BaseModel

from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY, SubscriptionModel
from orchestrator.core.domain.lifecycle import lookup_specialized_type
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.indexing.schema import iter_model_field_annotations
from orchestrator.core.types import SubscriptionLifecycle


def _model_types(annotation: Any) -> set[type[BaseModel]]:
    """Return Pydantic model types contained in an annotation."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return {annotation}
    return {model_type for arg in get_args(annotation) for model_type in _model_types(arg)}


def _collect_field_types(
    model_type: type[BaseModel],
    path: str,
    field_types: dict[str, set[FieldType]],
    ancestors: set[type[BaseModel]],
) -> None:
    if model_type in ancestors:
        return

    ancestors = ancestors | {model_type}
    for name, annotation in iter_model_field_annotations(model_type):
        field_path = f"{path}.{name}"
        is_list = get_origin(annotation) is list
        nested_model_types = _model_types(annotation)
        if nested_model_types:
            nested_path = f"{field_path}.*" if is_list else field_path
            for nested_model_type in nested_model_types:
                _collect_field_types(nested_model_type, nested_path, field_types, ancestors)
        else:
            indexed_path = f"{field_path}.*" if is_list else field_path
            field_types[indexed_path].add(FieldType.from_type_hint(annotation))


def _specialized_subscription_types(model_type: type[SubscriptionModel]) -> set[type[SubscriptionModel]]:
    """Return a registered subscription model together with its lifecycle-specialized variants.

    Uses the lifecycle registry maintained by ``register_specialized_type()`` instead of walking
    ``__subclasses__()``, so only variants actually registered for this model are included.
    """
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
    for model_type in model_types:
        _collect_field_types(model_type, "subscription", field_types, set())
    return {path: frozenset(types) for path, types in field_types.items()}


def clear_field_type_cache() -> None:
    """Clear cached subscription field types after changing the model registry."""
    _subscription_field_types.cache_clear()


def resolve_field_types(entity_type: EntityType, path: str) -> frozenset[FieldType]:
    """Return the Pydantic-derived index types for an exact or global field path."""
    if entity_type != EntityType.SUBSCRIPTION:
        return frozenset()

    field_types = _subscription_field_types()
    if "." in path:
        schema_path = ".".join("*" if segment.isdigit() else segment for segment in path.split("."))
        return field_types.get(schema_path, frozenset())
    return frozenset().union(
        *(types for field_path, types in field_types.items() if field_path.rsplit(".", maxsplit=1)[-1] == path)
    )
