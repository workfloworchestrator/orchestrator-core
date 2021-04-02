# Copyright 2019-2020 SURF.
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
    fixed_input,
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
)
from orchestrator.security import opa_security_default

api_router = APIRouter()
api_router.include_router(
    fixed_input.router,
    prefix="/fixed_inputs",
    tags=["Core", "Fixed Inputs"],
    dependencies=[Depends(opa_security_default)],
)
api_router.include_router(
    processes.router, prefix="/processes", tags=["Core", "Processes"], dependencies=[Depends(opa_security_default)]
)

api_router.include_router(
    product_blocks.router,
    prefix="/product_blocks",
    tags=["Core", "Product Blocks"],
    dependencies=[Depends(opa_security_default)],
)
api_router.include_router(
    products.router, prefix="/products", tags=["Core", "Product"], dependencies=[Depends(opa_security_default)]
)
api_router.include_router(
    resource_types.router,
    prefix="/resource_types",
    tags=["Core", "Resource Types"],
    dependencies=[Depends(opa_security_default)],
)
api_router.include_router(
    subscriptions.router,
    prefix="/subscriptions",
    tags=["Core", "Subscriptions"],
    dependencies=[Depends(opa_security_default)],
)
api_router.include_router(
    subscription_customer_descriptions.router,
    prefix="/subscription_customer_descriptions",
    tags=["Core", "Subscription Customer Descriptions"],
    dependencies=[Depends(opa_security_default)],
)
api_router.include_router(
    user.router, prefix="/user", tags=["Core", "User"], dependencies=[Depends(opa_security_default)]
)
api_router.include_router(
    workflows.router, prefix="/workflows", tags=["Core", "Workflows"], dependencies=[Depends(opa_security_default)]
)
api_router.include_router(
    settings.router, prefix="/settings", tags=["Core", "Settings"], dependencies=[Depends(opa_security_default)]
)
api_router.include_router(health.router, prefix="/health", tags=["Core"])
api_router.include_router(
    translations.router,
    prefix="/translations",
    tags=["Core", "Translations"],
)
