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

import inspect
from typing import Iterator

from fastapi.routing import APIRoute
from starlette.routing import BaseRoute, Router

# Endpoints that are still synchronous (`def` instead of `async def`).
#
# This allowlist must only ever SHRINK. All new endpoints must be `async def`,
# offloading blocking IO with `await run_in_threadpool(...)` or using
# `db.async_session()`. See https://github.com/workfloworchestrator/orchestrator-core/issues/1251
KNOWN_SYNC_ENDPOINTS: frozenset[str] = frozenset(
    {
        "orchestrator.core.api.api_v1.endpoints.mcp_tools.export_query_endpoint",
        "orchestrator.core.api.api_v1.endpoints.mcp_tools.get_process_status_endpoint",
        "orchestrator.core.api.api_v1.endpoints.mcp_tools.get_subscription_available_workflows_endpoint",
        "orchestrator.core.api.api_v1.endpoints.mcp_tools.get_subscription_details_endpoint",
        "orchestrator.core.api.api_v1.endpoints.mcp_tools.get_valid_operators_endpoint",
        "orchestrator.core.api.api_v1.endpoints.mcp_tools.get_workflow_form_endpoint",
        "orchestrator.core.api.api_v1.endpoints.mcp_tools.list_recent_processes_endpoint",
        "orchestrator.core.api.api_v1.endpoints.mcp_tools.list_workflows_endpoint",
        "orchestrator.core.api.api_v1.endpoints.mcp_tools.resolve_entity_endpoint",
        "orchestrator.core.api.api_v1.endpoints.processes.abort_process_endpoint",
        "orchestrator.core.api.api_v1.endpoints.processes.continue_awaiting_process_endpoint",
        "orchestrator.core.api.api_v1.endpoints.processes.delete",
        "orchestrator.core.api.api_v1.endpoints.processes.processes_filterable",
        "orchestrator.core.api.api_v1.endpoints.processes.show",
        "orchestrator.core.api.api_v1.endpoints.processes.status_counts",
        "orchestrator.core.api.api_v1.endpoints.processes.update_progress_on_awaiting_process_endpoint",
        "orchestrator.core.api.api_v1.endpoints.product_blocks.get_product_block_description",
        "orchestrator.core.api.api_v1.endpoints.products.fetch",
        "orchestrator.core.api.api_v1.endpoints.products.product_by_id",
        "orchestrator.core.api.api_v1.endpoints.resource_types.get_resource_type_description",
        "orchestrator.core.api.api_v1.endpoints.settings.get_cache_names",
        "orchestrator.core.api.api_v1.endpoints.settings.get_exposed_settings",
        "orchestrator.core.api.api_v1.endpoints.settings.get_global_status",
        "orchestrator.core.api.api_v1.endpoints.settings.get_worker_status",
        "orchestrator.core.api.api_v1.endpoints.subscription_customer_descriptions.delete_subscription_customer_descriptions",
        "orchestrator.core.api.api_v1.endpoints.subscription_customer_descriptions.get_subscription_customer_description_by_customer_subscription",
        "orchestrator.core.api.api_v1.endpoints.subscription_customer_descriptions.get_subscription_customer_descriptions",
        "orchestrator.core.api.api_v1.endpoints.subscriptions.subscription_set_in_sync",
        "orchestrator.core.api.api_v1.endpoints.subscriptions.subscription_workflows_by_id",
        "orchestrator.core.api.api_v1.endpoints.subscriptions.subscriptions_search",
        "orchestrator.core.api.api_v1.endpoints.translations.get_translations",
        "orchestrator.core.api.api_v1.endpoints.user.log_error",
        "orchestrator.core.api.api_v1.endpoints.user.log_user_info",
        "orchestrator.core.api.api_v1.endpoints.workflows.get_workflow_description",
        "orchestrator.core.app.OrchestratorCore.__init__.<locals>._index",
    }
)


def _qualified_name(route: APIRoute) -> str:
    endpoint = inspect.unwrap(route.endpoint)
    return f"{endpoint.__module__}.{endpoint.__qualname__}"


def _iter_api_routes(router: Router) -> Iterator[APIRoute]:
    """Yield every ``APIRoute`` reachable from ``router``.

    Since FastAPI 0.138 / Starlette 1.3, ``include_router`` no longer flattens
    child routes into the parent; it wraps them in a lazy ``_IncludedRouter``
    exposed via ``original_router``. Recurse through those so nested endpoints
    remain visible to this guardrail.
    """
    routes: list[BaseRoute] = getattr(router, "routes", [])
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            yield from _iter_api_routes(original_router)


def test_no_new_sync_endpoints(fastapi_app):
    sync_endpoints = {
        _qualified_name(route)
        for route in _iter_api_routes(fastapi_app.router)
        if not inspect.iscoroutinefunction(inspect.unwrap(route.endpoint))
    }
    added = sorted(sync_endpoints - KNOWN_SYNC_ENDPOINTS)
    converted = sorted(KNOWN_SYNC_ENDPOINTS - sync_endpoints)
    assert sync_endpoints == KNOWN_SYNC_ENDPOINTS, (
        f"New sync endpoints (must be `async def`, see issue #1251): {added}\n"
        f"Endpoints no longer sync (remove from KNOWN_SYNC_ENDPOINTS): {converted}"
    )
