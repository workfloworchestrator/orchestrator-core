# Copyright 2022-2023 SURF.
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
from orchestrator.graphql.autoregistration import (
    EnumDict,
    add_class_to_strawberry,
    graphql_subscription_name,
    register_domain_models,
)
from orchestrator.graphql.schema import (
    GRAPHQL_MODELS,
    Mutation,
    OrchestratorGraphqlRouter,
    OrchestratorSchema,
    Query,
    create_graphql_router,
    custom_context_dependency,
    get_context,
    graphql_router,
)
from orchestrator.graphql.types import SCALAR_OVERRIDES

__all__ = [
    "GRAPHQL_MODELS",
    "SCALAR_OVERRIDES",
    "Query",
    "Mutation",
    "OrchestratorGraphqlRouter",
    "OrchestratorSchema",
    "custom_context_dependency",
    "get_context",
    "graphql_router",
    "create_graphql_router",
    "EnumDict",
    "add_class_to_strawberry",
    "graphql_subscription_name",
    "register_domain_models",
]
