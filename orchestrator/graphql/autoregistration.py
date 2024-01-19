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
from typing import Any

import strawberry
import structlog
from strawberry.experimental.pydantic.conversion_types import StrawberryTypeFromPydantic
from strawberry.federation.schema_directives import Key
from strawberry.unset import UNSET

from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import DomainModel, get_depends_on_product_block_type_list
from orchestrator.graphql.schemas import StrawberryModelType
from orchestrator.utils.helpers import to_camel

logger = structlog.get_logger(__name__)

EnumDict = dict[str, EnumMeta]


def create_strawberry_enum(enum: Any) -> EnumMeta:
    return strawberry.enum(enum)


def is_not_strawberry_enum(key: str, strawberry_enums: EnumDict) -> bool:
    return key not in strawberry_enums


def is_enum(field: Any) -> bool:
    return inspect.isclass(field) and issubclass(field, Enum)


def create_strawberry_enums(model: type[DomainModel], strawberry_enums: EnumDict) -> EnumDict:
    enums = {
        key: create_strawberry_enum(field)
        for key, field in model._non_product_block_fields_.items()
        if is_enum(field) and is_not_strawberry_enum(key, strawberry_enums)
    }
    return strawberry_enums | enums


def graphql_name(name: str) -> str:
    return to_camel(name.replace(" ", "_"))


def graphql_subscription_name(name: str) -> str:
    subscription_graphql_name = graphql_name(name).replace("Initial", "").replace("Inactive", "")
    return f"{subscription_graphql_name}Subscription"


def create_block_strawberry_type(
    strawberry_name: str,
    model: type[DomainModel],
) -> type[StrawberryTypeFromPydantic[DomainModel]]:
    from strawberry.federation.schema_directives import Key
    from strawberry.unset import UNSET

    federation_key_directives = [Key(fields="subscriptionInstanceId", resolvable=UNSET)]

    if keys := [key for key in model.__annotations__.keys() if "_id" in key]:
        federation_key_directives.extend([Key(fields=to_camel(key), resolvable=UNSET) for key in keys])

    new_type = type(strawberry_name, (), {})
    strawberry_wrapper = strawberry.experimental.pydantic.type(
        model, name=strawberry_name, all_fields=True, directives=federation_key_directives
    )
    return strawberry_wrapper(new_type)


def create_subscription_strawberry_type(strawberry_name: str, model: type[DomainModel], interface: type) -> type:
    base_type = type(strawberry_name, (interface,), {})
    directives = [Key(fields="subscriptionId", resolvable=UNSET)]

    pydantic_wrapper = strawberry.experimental.pydantic.type(
        model, all_fields=True, directives=directives, description=f"{strawberry_name} Type"
    )
    return type(strawberry_name, (pydantic_wrapper(base_type),), {})


def add_class_to_strawberry(
    model_name: str,
    model: type[DomainModel],
    strawberry_models: StrawberryModelType,
    strawberry_enums: EnumDict,
    interface: type | None = None,
) -> None:
    if model_name in strawberry_models:
        logger.debug("Skip already registered strawberry model", model=repr(model), strawberry_name=model_name)
        return
    logger.debug("Registering strawberry model", model=repr(model), strawberry_name=model_name)

    strawberry_enums = create_strawberry_enums(model, strawberry_enums)

    product_blocks_types_in_model = get_depends_on_product_block_type_list(model._get_depends_on_product_block_types())
    for field in product_blocks_types_in_model:
        graphql_field_name = graphql_name(field.__name__)
        if graphql_field_name not in strawberry_models and graphql_field_name != model_name:
            add_class_to_strawberry(graphql_field_name, field, strawberry_models, strawberry_enums)

    if interface:
        strawberry_models[model_name] = create_subscription_strawberry_type(model_name, model, interface)
    else:
        strawberry_models[model_name] = create_block_strawberry_type(model_name, model)
    logger.debug("Registered strawberry model", model=repr(model), strawberry_name=model_name)


def register_domain_models(
    interface: type | None, existing_models: StrawberryModelType | None = None
) -> StrawberryModelType:
    strawberry_models = existing_models if existing_models else {}
    strawberry_enums: EnumDict = {}
    products = {
        product_type.__base_type__.__name__: product_type.__base_type__
        for product_type in SUBSCRIPTION_MODEL_REGISTRY.values()
        if product_type.__base_type__
    }
    for key, product_type in products.items():
        add_class_to_strawberry(
            interface=interface,
            model_name=graphql_subscription_name(key),
            model=product_type,
            strawberry_models=strawberry_models,
            strawberry_enums=strawberry_enums,
        )
    return strawberry_models
