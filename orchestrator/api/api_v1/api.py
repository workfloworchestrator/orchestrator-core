# Copyright 2019-2020 SURF, GÉANT.
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

"""Module that implements process related API endpoints."""

from fastapi.param_functions import Depends
from fastapi.routing import APIRouter

from orchestrator.api.api_v1.endpoints import (
    health,
    processes,
    product_blocks,
    products,
    resource_types,
    settings,
    subscription_customer_descriptions,
    subscriptions,
    translations,
    user,
    workflows,
    ws,
)
from orchestrator.security import authorize

api_router = APIRouter()

api_router.include_router(
    processes.router, prefix="/processes", tags=["Core", "Processes"], dependencies=[Depends(authorize)]
)
api_router.include_router(
    subscriptions.router,
    prefix="/subscriptions",
    tags=["Core", "Subscriptions"],
    dependencies=[Depends(authorize)],
)
api_router.include_router(processes.ws_router, prefix="/processes", tags=["Core", "Processes"])
api_router.include_router(
    products.router, prefix="/products", tags=["Core", "Product"], dependencies=[Depends(authorize)]
)
api_router.include_router(
    product_blocks.router,
    prefix="/product_blocks",
    tags=["Core", "Product Blocks"],
    dependencies=[Depends(authorize)],
)
api_router.include_router(
    resource_types.router,
    prefix="/resource_types",
    tags=["Core", "Resource Types"],
    dependencies=[Depends(authorize)],
)
api_router.include_router(
    workflows.router,
    prefix="/workflows",
    tags=["Core", "Workflows"],
    dependencies=[Depends(authorize)],
)
api_router.include_router(
    subscription_customer_descriptions.router,
    prefix="/subscription_customer_descriptions",
    tags=["Core", "Subscription Customer Descriptions"],
    dependencies=[Depends(authorize)],
)
api_router.include_router(user.router, prefix="/user", tags=["Core", "User"], dependencies=[Depends(authorize)])
api_router.include_router(
    settings.router, prefix="/settings", tags=["Core", "Settings"], dependencies=[Depends(authorize)]
)
api_router.include_router(settings.ws_router, prefix="/settings", tags=["Core", "Settings"])
api_router.include_router(health.router, prefix="/health", tags=["Core"])
api_router.include_router(
    translations.router,
    prefix="/translations",
    tags=["Core", "Translations"],
)
api_router.include_router(ws.router, prefix="/ws", tags=["Core", "Events"])
