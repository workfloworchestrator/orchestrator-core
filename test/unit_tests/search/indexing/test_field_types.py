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

"""Tests for orchestrator.core.search.indexing.field_types: subscription field type indexing and resolution."""

from collections import defaultdict
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, Field

from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.core.domain.base import SubscriptionModel
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.indexing.field_types import (
    _collect_field_types,
    clear_field_type_cache,
    resolve_field_types,
)
from test.unit_tests.search.fixtures.blocks import BasicBlock, ComputedBlock


def test_collect_field_types_stops_at_self_referential_ancestor() -> None:
    """A model that references itself must not recurse infinitely."""

    class RecursiveModel(BaseModel):
        name: str
        child: "RecursiveModel | None" = None

    RecursiveModel.model_rebuild()

    field_types: dict[str, set[FieldType]] = defaultdict(set)
    _collect_field_types(RecursiveModel, "subscription", field_types, set())

    assert dict(field_types) == {"subscription.name": {FieldType.STRING}}


def test_resolve_field_types_non_subscription_entity_returns_empty() -> None:
    assert resolve_field_types(EntityType.WORKFLOW, "name") == frozenset()


def test_clear_field_type_cache_refreshes_registered_models() -> None:
    class InitialSubscription(SubscriptionModel, is_base=True):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        initial_field: str

    class RegisteredLaterSubscription(SubscriptionModel, is_base=True):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        registered_later_field: int

    with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"INITIAL": InitialSubscription}, clear=True):
        clear_field_type_cache()
        assert resolve_field_types(EntityType.SUBSCRIPTION, "registered_later_field") == frozenset()

        SUBSCRIPTION_MODEL_REGISTRY["REGISTERED_LATER"] = RegisteredLaterSubscription
        clear_field_type_cache()

        assert resolve_field_types(EntityType.SUBSCRIPTION, "registered_later_field") == frozenset({FieldType.INTEGER})

    clear_field_type_cache()


def test_resolve_field_types_resolves_nested_block_path() -> None:
    class BlockSubscription(SubscriptionModel, is_base=True):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        basic_block: BasicBlock

    clear_field_type_cache()
    with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"BLOCK": BlockSubscription}, clear=True):
        types = resolve_field_types(EntityType.SUBSCRIPTION, "subscription.basic_block.value")
    clear_field_type_cache()

    assert types == frozenset({FieldType.INTEGER})


def test_resolve_field_types_uses_domain_field_registries() -> None:
    class DomainFieldsSubscription(SubscriptionModel, is_base=True):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        renamed_value: int = Field(alias="value")
        basic_block: BasicBlock
        computed_block: ComputedBlock

    clear_field_type_cache()
    with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"DOMAIN": DomainFieldsSubscription}, clear=True):
        scalar_types = resolve_field_types(EntityType.SUBSCRIPTION, "subscription.value")
        nested_types = resolve_field_types(EntityType.SUBSCRIPTION, "subscription.basic_block.value")
        computed_types = resolve_field_types(EntityType.SUBSCRIPTION, "subscription.computed_block.display_name")
    clear_field_type_cache()

    assert scalar_types == frozenset({FieldType.INTEGER})
    assert nested_types == frozenset({FieldType.INTEGER})
    assert computed_types == frozenset({FieldType.STRING})


def test_resolve_field_types_global_path_matches_any_depth() -> None:
    """A dotless path (no ltree segments) matches the field name at any depth."""

    class BlockSubscription(SubscriptionModel, is_base=True):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        basic_block: BasicBlock

    clear_field_type_cache()
    with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"BLOCK": BlockSubscription}, clear=True):
        types = resolve_field_types(EntityType.SUBSCRIPTION, "value")
    clear_field_type_cache()

    assert types == frozenset({FieldType.INTEGER})


def test_resolve_field_types_unknown_path_returns_empty() -> None:
    class SimpleSubscription(SubscriptionModel, is_base=True):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        name: str

    clear_field_type_cache()
    with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"SIMPLE": SimpleSubscription}, clear=True):
        types = resolve_field_types(EntityType.SUBSCRIPTION, "subscription.does_not_exist")
    clear_field_type_cache()

    assert types == frozenset()
