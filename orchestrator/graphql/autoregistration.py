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
import structlog
from strawberry.experimental.pydantic.conversion_types import StrawberryTypeFromPydantic

from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import DomainModel, get_depends_on_product_block_type_list
from orchestrator.graphql.schema import GRAPHQL_MODELS, StrawberryModelType
from orchestrator.graphql.schemas.subscription import SubscriptionInterface
from orchestrator.utils.helpers import to_camel

logger = structlog.get_logger(__name__)

EnumDict = dict[str, EnumMeta]


def create_strawberry_enum(enum: Any) -> EnumMeta:
    return strawberry.enum(enum)


def is_not_strawberry_enum(key: str, strawberry_enums: EnumDict) -> bool:
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
    base_type = type(strawberry_name, (SubscriptionInterface,), {})
    pydantic_wrapper = strawberry.experimental.pydantic.type(model, all_fields=True)
    federation_wrapper = strawberry.federation.type(description=f"{strawberry_name} Type", keys=["subscriptionId"])
    pydantic_type = pydantic_wrapper(base_type)
    federation_type = type(strawberry_name, (pydantic_type,), {})
    strawberry_type = federation_wrapper(federation_type)

    def from_pydantic(model: pydantic_type) -> strawberry_type:  # type: ignore
        graphql_model = pydantic_type.from_pydantic(model)
        graphql_model.__class__ = strawberry_type
        return graphql_model

    strawberry_type.from_pydantic = from_pydantic  # type: ignore
    return strawberry_type


def create_block_strawberry_type(
    strawberry_name: str, model: Type[DomainModel]
) -> Type[StrawberryTypeFromPydantic[DomainModel]]:
    new_type = type(strawberry_name, (), {})
    strawberry_wrapper = strawberry.experimental.pydantic.type(model, all_fields=True)
    return strawberry_wrapper(new_type)


def create_strawberry_enums(model: Type[DomainModel], strawberry_enums: EnumDict) -> EnumDict:
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
    strawberry_enums: EnumDict,
    with_interface: bool = False,
) -> None:
    if model_name in strawberry_models:
        logger.debug("Skip already registered strawberry model", model=repr(model), strawberry_name=model_name)
        return
    logger.debug("Registering strawberry model", model=repr(model), strawberry_name=model_name)

    strawberry_enums = create_strawberry_enums(model, strawberry_enums)

    product_blocks_types_in_model = get_depends_on_product_block_type_list(model._get_depends_on_product_block_types())
    for field in product_blocks_types_in_model:
        graphql_field_name = graphql_name(field.__name__)
        if is_not_strawberry_type(graphql_field_name, strawberry_models) and graphql_field_name != model_name:
            add_class_to_strawberry(graphql_field_name, field, strawberry_models, strawberry_enums)

    strawberry_type_convert_function = (
        create_subscription_strawberry_type if with_interface else create_block_strawberry_type
    )
    strawberry_models[model_name] = strawberry_type_convert_function(model_name, model)


def register_domain_models() -> None:
    strawberry_models = GRAPHQL_MODELS
    strawberry_enums: EnumDict = {}
    products = {
        product_type.__base_type__.__name__: product_type.__base_type__
        for product_type in SUBSCRIPTION_MODEL_REGISTRY.values()
        if product_type.__base_type__
    }
    for key, product_type in products.items():
        add_class_to_strawberry(
            model_name=graphql_subscription_name(key),
            model=product_type,
            strawberry_models=strawberry_models,
            strawberry_enums=strawberry_enums,
            with_interface=True,
        )
