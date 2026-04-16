# Copyright 2019-2026 SURF.
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

from orchestrator.graphql.resolvers.customer import resolve_customer
from orchestrator.graphql.resolvers.process import resolve_process, resolve_processes
from orchestrator.graphql.resolvers.product import resolve_products
from orchestrator.graphql.resolvers.product_block import resolve_product_blocks
from orchestrator.graphql.resolvers.resource_type import resolve_resource_types
from orchestrator.graphql.resolvers.search import (
    resolve_search,
    resolve_search_definitions,
    resolve_search_paths,
    resolve_search_query,
    resolve_search_query_export,
    resolve_search_query_results,
)
from orchestrator.graphql.resolvers.settings import SettingsMutation, resolve_settings
from orchestrator.graphql.resolvers.subscription import resolve_subscription, resolve_subscriptions
from orchestrator.graphql.resolvers.version import resolve_version
from orchestrator.graphql.resolvers.workflow import resolve_workflows

__all__ = [
    "resolve_process",
    "resolve_processes",
    "resolve_products",
    "resolve_product_blocks",
    "resolve_settings",
    "SettingsMutation",
    "resolve_subscription",
    "resolve_subscriptions",
    "resolve_customer",
    "resolve_resource_types",
    "resolve_workflows",
    "resolve_version",
    "resolve_search",
    "resolve_search_definitions",
    "resolve_search_paths",
    "resolve_search_query",
    "resolve_search_query_export",
    "resolve_search_query_results",
]
