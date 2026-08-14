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

from unittest.mock import patch

from pydantic import ConfigDict, Field

from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.core.domain.base import ProductBlockModel, SubscriptionModel
from orchestrator.core.search.core.types import EntityType, FieldType, UIType
from orchestrator.core.search.indexing.field_types import (
    clear_field_type_cache,
    resolve_field_types,
    resolve_field_value_kind,
)
from test.unit_tests.search.fixtures.blocks import BasicBlock, ComputedBlock, ListBlock


def test_resolve_field_types_handles_recursive_subscription_model() -> None:
    class RecursiveSubscription(SubscriptionModel, is_base=True):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        name: str
        child: "RecursiveSubscription | None" = None

    RecursiveSubscription.model_rebuild()

    clear_field_type_cache()
    with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"RECURSIVE": RecursiveSubscription}, clear=True):
        types = resolve_field_types(EntityType.SUBSCRIPTION, "subscription.name")
    clear_field_type_cache()

    assert types == frozenset({FieldType.STRING})


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


def test_resolve_field_types_indexes_annotated_list_fields_with_wildcard_path() -> None:
    class ListSubscription(SubscriptionModel, is_base=True):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        list_block: ListBlock

    clear_field_type_cache()
    with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"LIST": ListSubscription}, clear=True):
        types = resolve_field_types(EntityType.SUBSCRIPTION, "subscription.list_block.required_ids.0")
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


def test_resolve_field_types_includes_inherited_subscription_fields() -> None:
    class InheritedFieldsSubscription(SubscriptionModel, is_base=True):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        own_field: str

    clear_field_type_cache()
    try:
        with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"INHERITED": InheritedFieldsSubscription}, clear=True):
            customer_id_types = resolve_field_types(EntityType.SUBSCRIPTION, "subscription.customer_id")
            description_types = resolve_field_types(EntityType.SUBSCRIPTION, "subscription.description")
            note_types = resolve_field_types(EntityType.SUBSCRIPTION, "subscription.note")
            product_name_types = resolve_field_types(EntityType.SUBSCRIPTION, "subscription.product.name")
    finally:
        clear_field_type_cache()

    assert customer_id_types == frozenset({FieldType.STRING})
    assert description_types == frozenset({FieldType.STRING})
    assert note_types == frozenset({FieldType.STRING})
    assert product_name_types == frozenset({FieldType.STRING})


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


def test_resolve_field_value_kind_returns_only_unambiguous_types() -> None:
    class StringBlock(ProductBlockModel):
        ambiguous_value: str

    class NumericBlock(ProductBlockModel):
        ambiguous_value: int

    class BlockSubscription(SubscriptionModel, is_base=True):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        string_value: str
        numeric_value: int
        string_block: StringBlock
        numeric_block: NumericBlock

    clear_field_type_cache()
    with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"BLOCK": BlockSubscription}, clear=True):
        string_kind = resolve_field_value_kind(EntityType.SUBSCRIPTION, "string_value")
        numeric_kind = resolve_field_value_kind(EntityType.SUBSCRIPTION, "numeric_value")
        ambiguous_kind = resolve_field_value_kind(EntityType.SUBSCRIPTION, "ambiguous_value")
        qualified_string_kind = resolve_field_value_kind(
            EntityType.SUBSCRIPTION, "subscription.string_block.ambiguous_value"
        )
        qualified_numeric_kind = resolve_field_value_kind(
            EntityType.SUBSCRIPTION, "subscription.numeric_block.ambiguous_value"
        )
        other_entity_kind = resolve_field_value_kind(EntityType.WORKFLOW, "string_value")
    clear_field_type_cache()

    assert string_kind == UIType.STRING
    assert numeric_kind == UIType.NUMBER
    assert ambiguous_kind is None
    assert qualified_string_kind == UIType.STRING
    assert qualified_numeric_kind == UIType.NUMBER
    assert other_entity_kind is None


def test_resolve_field_types_unknown_path_returns_empty() -> None:
    class SimpleSubscription(SubscriptionModel, is_base=True):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        name: str

    clear_field_type_cache()
    with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"SIMPLE": SimpleSubscription}, clear=True):
        types = resolve_field_types(EntityType.SUBSCRIPTION, "subscription.does_not_exist")
    clear_field_type_cache()

    assert types == frozenset()
