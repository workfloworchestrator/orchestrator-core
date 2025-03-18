# Copyright 2019-2025 SURF.
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

"""Functions to transform result of query SubscriptionInstanceAsJsonFunction to match the ProductBlockModel."""

from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Iterable

from more_itertools import first, only

from orchestrator.types import is_list_type, is_optional_type

if TYPE_CHECKING:
    from orchestrator.domain.base import ProductBlockModel


def _ensure_list(instance_or_value_list: Any) -> Any:
    if instance_or_value_list is None:
        return []

    return instance_or_value_list


def _instance_list_to_dict(product_block_field_type: type, instance_list: Any) -> Any:
    if instance_list is None:
        return None

    match instance_list:
        case list():
            if instance := only(instance_list):
                return instance

            if not is_optional_type(product_block_field_type):
                raise ValueError("Required subscription instance is missing in database")

            return None  # Set the optional product block field to None
        case _:
            raise ValueError(f"All subscription instances should be returned as list, found {type(instance_list)}")  #


def _value_list_to_value(field_type: type, value_list: Any) -> Any:
    if value_list is None:
        return None

    match value_list:
        case list():
            if (value := only(value_list)) is not None:
                return value

            if not is_optional_type(field_type):
                raise ValueError("Required subscription value is missing in database")

            return None  # Set the optional resource type field to None
        case _:
            raise ValueError(f"All instance values should be returned as list, found {type(value_list)}")


def field_transformation_rules(klass: type["ProductBlockModel"]) -> dict[str, Callable]:
    """Create mapping of transformation rules for the given product block type."""

    def create_rules() -> Iterable[tuple[str, Callable]]:
        for field_name, product_block_field_type in klass._product_block_fields_.items():
            if is_list_type(product_block_field_type):
                yield field_name, _ensure_list
            else:
                yield field_name, partial(_instance_list_to_dict, product_block_field_type)

        for field_name, field_type in klass._non_product_block_fields_.items():
            if is_list_type(field_type):
                yield field_name, _ensure_list
            else:
                yield field_name, partial(_value_list_to_value, field_type)

    return dict(create_rules())


def transform_instance_fields(all_rules: dict[str, dict[str, Callable]], instance: dict) -> None:
    """Apply transformation rules to the given subscription instance dict."""

    from orchestrator.domain.base import ProductBlockModel

    # Lookup applicable rules through product block name
    field_rules = all_rules[instance["name"]]

    klass = ProductBlockModel.registry[instance["name"]]

    # Ensure the product block's metadata is loaded
    klass._fix_pb_data()

    # Transform all fields in this subscription instance
    try:
        for field_name, rewrite_func in field_rules.items():
            field_value = instance.get(field_name)
            instance[field_name] = rewrite_func(field_value)
    except ValueError as e:
        raise ValueError(f"Invalid subscription instance data {instance}") from e

    # Recurse into nested subscription instances
    for field_value in instance.values():
        if isinstance(field_value, dict):
            transform_instance_fields(all_rules, field_value)
        if isinstance(field_value, list) and isinstance(first(field_value, None), dict):
            for list_value in field_value:
                transform_instance_fields(all_rules, list_value)
