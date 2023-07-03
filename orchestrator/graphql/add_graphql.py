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

from orchestrator import OrchestratorCore
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import DomainModel, SubscriptionModel, get_depends_on_product_block_type_list
from orchestrator.graphql.schema import GRAPHQL_MODELS, Query, StrawberryModelType, create_graphql_router
from orchestrator.graphql.schemas.subscription import SubscriptionInterface
from orchestrator.graphql.types import CustomInfo
from orchestrator.utils.helpers import to_camel

EnumList = dict[str, EnumMeta]


def create_strawberry_enum(enum: Any) -> EnumMeta:
    return strawberry.enum(enum)


def is_not_strawberry_type(key: str, strawberry_models: StrawberryModelType) -> bool:
    return key.replace(" ", "_") not in strawberry_models


def is_not_strawberry_enum(key: str, strawberry_enums: EnumList) -> bool:
    return key not in strawberry_enums


def is_enum(field: Any) -> bool:
    return inspect.isclass(field) and issubclass(field, Enum)


def graphql_name(name: str) -> str:
    return f"{name.replace(' ', '_').replace('Initial', '').replace('Inactive', '')}Subscription"


def add_class_to_strawberry(
    model_name: str,
    model: Type[DomainModel],
    strawberry_models: StrawberryModelType,
    strawberry_enums: EnumList,
    with_interface: bool = False,
) -> None:
    enums = {
        key: field
        for key, field in model._non_product_block_fields_.items()
        if is_enum(field) and is_not_strawberry_enum(key, strawberry_enums)
    }
    strawberry_enums = strawberry_enums | {key: create_strawberry_enum(field) for key, field in enums.items()}

    product_blocks_types_in_model = get_depends_on_product_block_type_list(model._get_depends_on_product_block_types())
    for field in product_blocks_types_in_model:
        if is_not_strawberry_type(field.__name__, strawberry_models) and field.__name__ != model_name:
            add_class_to_strawberry(field.__name__, field, strawberry_models, strawberry_enums)

    strawberry_name = to_camel(model_name.replace(" ", "_"))
    if with_interface:
        base_type = type(strawberry_name, (SubscriptionInterface,), {})  # type: ignore
        straw_wrapper = strawberry.experimental.pydantic.type(model, all_fields=True)
        federation_wrapper = strawberry.federation.type(description=f"{strawberry_name} Type", keys=["subscriptionId"])
        pydantic_type = straw_wrapper(base_type)
        temp = type(strawberry_name, (pydantic_type,), {})  # type: ignore
        strawberry_type = federation_wrapper(temp)

        def from_pydantic(model: pydantic_type) -> strawberry_type:  # type: ignore
            graphql_model = pydantic_type.from_pydantic(model)
            graphql_model.__class__ = strawberry_type
            return graphql_model  # type: ignore

        strawberry_type.from_pydantic = from_pydantic  # type: ignore
    else:
        new_type = type(strawberry_name, (), {})  # type: ignore
        straw_wrapper = strawberry.experimental.pydantic.type(model, all_fields=True)
        strawberry_type = straw_wrapper(new_type)

    strawberry_models[strawberry_name] = strawberry_type


def add_graphql(app: OrchestratorCore) -> OrchestratorCore:
    strawberry_models = GRAPHQL_MODELS
    strawberry_enums: EnumList = {}
    products = {
        product_type.__base_type__.__name__: product_type.__base_type__
        for product_type in SUBSCRIPTION_MODEL_REGISTRY.values()
        if product_type.__base_type__
    }
    for key, product_type in products.items():
        add_class_to_strawberry(graphql_name(key), product_type, strawberry_models, strawberry_enums, True)

    def sub_resolver(info: CustomInfo, id: str) -> SubscriptionInterface:  # type: ignore
        subscription = SubscriptionModel.from_subscription(id)
        return strawberry_models[graphql_name(subscription.__base_type__.__name__)].from_pydantic(subscription)  # type: ignore

    @strawberry.type(description="Orchestrator queries")
    class UpdatedQuery(Query):
        subscription_detail = strawberry.field(sub_resolver)

    new_router = create_graphql_router(UpdatedQuery)
    app.include_router(new_router, prefix="/api/graphql")
    return app
