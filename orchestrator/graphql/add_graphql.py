# Copyright 2019-2023 SURF.
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

import inspect
from enum import Enum, EnumMeta
from typing import Any, Type

import strawberry
from strawberry.experimental.pydantic.conversion_types import StrawberryTypeFromPydantic

from orchestrator.domain.base import DomainModel, get_depends_on_product_block_type_list
from orchestrator.graphql.schema import StrawberryModelType
from orchestrator.graphql.schemas.subscription import SubscriptionInterface
from orchestrator.utils.helpers import to_camel

EnumList = dict[str, EnumMeta]


def create_strawberry_enum(enum: Any) -> EnumMeta:
    return strawberry.enum(enum)


def is_not_strawberry_enum(key: str, strawberry_enums: EnumList) -> bool:
    return key not in strawberry_enums


def is_enum(field: Any) -> bool:
    return inspect.isclass(field) and issubclass(field, Enum)


def graphql_name(name: str) -> str:
    return to_camel(name.replace(" ", "_").replace("Initial", "").replace("Inactive", ""))


def graphql_subscription_name(name: str) -> str:
    return f"{graphql_name(name)}Subscription"


def is_not_strawberry_type(key: str, strawberry_models: StrawberryModelType) -> bool:
    return graphql_name(key) not in strawberry_models


def create_subscription_strawberry_type(strawberry_name: str, model: Type[DomainModel]) -> Type[SubscriptionInterface]:
    base_type = type(strawberry_name, (SubscriptionInterface,), {})  # type: ignore
    pydantic_wrapper = strawberry.experimental.pydantic.type(model, all_fields=True)
    federation_wrapper = strawberry.federation.type(description=f"{strawberry_name} Type", keys=["subscriptionId"])
    pydantic_type = pydantic_wrapper(base_type)
    federation_type = type(strawberry_name, (pydantic_type,), {})  # type: ignore
    strawberry_type = federation_wrapper(federation_type)

    def from_pydantic(model: pydantic_type) -> strawberry_type:  # type: ignore
        graphql_model = pydantic_type.from_pydantic(model)
        graphql_model.__class__ = strawberry_type
        return graphql_model  # type: ignore

    strawberry_type.from_pydantic = from_pydantic  # type: ignore
    return strawberry_type


def create_block_strawberry_type(
    strawberry_name: str, model: Type[DomainModel]
) -> Type[StrawberryTypeFromPydantic[DomainModel]]:
    new_type = type(strawberry_name, (), {})  # type: ignore
    strawberry_wrapper = strawberry.experimental.pydantic.type(model, all_fields=True)
    return strawberry_wrapper(new_type)


def create_strawberry_enums(model: Type[DomainModel], strawberry_enums: EnumList) -> EnumList:
    enums = {
        key: field
        for key, field in model._non_product_block_fields_.items()
        if is_enum(field) and is_not_strawberry_enum(key, strawberry_enums)
    }
    return strawberry_enums | {key: create_strawberry_enum(field) for key, field in enums.items()}


def add_class_to_strawberry(
    model_name: str,
    model: Type[DomainModel],
    strawberry_models: StrawberryModelType,
    strawberry_enums: EnumList,
    with_interface: bool = False,
) -> None:
    strawberry_enums = create_strawberry_enums(model, strawberry_enums)

    product_blocks_types_in_model = get_depends_on_product_block_type_list(model._get_depends_on_product_block_types())
    for field in product_blocks_types_in_model:
        if is_not_strawberry_type(field.__name__, strawberry_models) and field.__name__ != model_name:
            add_class_to_strawberry(field.__name__, field, strawberry_models, strawberry_enums)

    strawberry_name = graphql_name(model_name)
    strawberry_type_convert_function = (
        create_subscription_strawberry_type if with_interface else create_block_strawberry_type
    )
    strawberry_models[strawberry_name] = strawberry_type_convert_function(strawberry_name, model)
