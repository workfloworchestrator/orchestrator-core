#!/usr/bin/env python3

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
import sys
from typing import Any, Callable, Dict, Optional, Type

import sentry_sdk
import structlog
import typer
from fastapi.applications import FastAPI
from fastapi_etag.dependency import add_exception_handler
from nwastdlib.logging import initialise_logging

# This is needed to avoid having a maintenance version of nwa-stdlib for py<3.10
if sys.version_info >= (3, 10):
    from nwastdlib.logging import ClearStructlogContextASGIMiddleware

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse, Response

from orchestrator import __version__
from orchestrator.api.api_v1.api import api_router
from orchestrator.api.error_handling import ProblemDetailException
from orchestrator.cli.main import app as cli_app
from orchestrator.db import db, init_database
from orchestrator.db.database import DBSessionMiddleware
from orchestrator.distlock import init_distlock_manager
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY, SubscriptionModel
from orchestrator.exception_handlers import form_error_handler, problem_detail_handler
from orchestrator.forms import FormException
from orchestrator.services.processes import ProcessDataBroadcastThread
from orchestrator.settings import AppSettings, app_settings, tracer_provider
from orchestrator.version import GIT_COMMIT_HASH
from orchestrator.websocket import init_websocket_manager

logger = structlog.get_logger(__name__)


class OrchestratorCore(FastAPI):
    def __init__(
        self,
        title: str = "The Orchestrator",
        description: str = "The orchestrator is a project that enables users to run workflows.",
        openapi_url: str = "/api/openapi.json",
        docs_url: str = "/api/docs",
        redoc_url: str = "/api/redoc",
        version: str = __version__,
        default_response_class: Type[Response] = JSONResponse,
        base_settings: AppSettings = app_settings,
        **kwargs: Any,
    ) -> None:
        websocket_manager = init_websocket_manager(base_settings)
        distlock_manager = init_distlock_manager(base_settings)
        self.broadcast_thread = ProcessDataBroadcastThread(websocket_manager)

        startup_functions: list[Callable] = [distlock_manager.connect_redis]
        shutdown_functions: list[Callable] = [distlock_manager.disconnect_redis]
        if websocket_manager.enabled:
            startup_functions.extend([websocket_manager.connect_redis, self.broadcast_thread.start])
            shutdown_functions.extend(
                [websocket_manager.disconnect_all, self.broadcast_thread.stop, websocket_manager.disconnect_redis]
            )

        super().__init__(
            title=title,
            description=description,
            openapi_url=openapi_url,
            docs_url=docs_url,
            redoc_url=redoc_url,
            version=version,
            default_response_class=default_response_class,
            on_startup=startup_functions,
            on_shutdown=shutdown_functions,
            **kwargs,
        )

        initialise_logging()

        self.include_router(api_router, prefix="/api")

        init_database(base_settings)

        # This is needed to avoid having a maintenance version of nwa-stdlib for py<3.10
        if sys.version_info >= (3, 10):
            self.add_middleware(ClearStructlogContextASGIMiddleware)
        self.add_middleware(SessionMiddleware, secret_key=base_settings.SESSION_SECRET)
        self.add_middleware(DBSessionMiddleware, database=db)
        origins = base_settings.CORS_ORIGINS.split(",")
        self.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=base_settings.CORS_ALLOW_METHODS,
            allow_headers=base_settings.CORS_ALLOW_HEADERS,
            expose_headers=base_settings.CORS_EXPOSE_HEADERS,
        )

        self.add_exception_handler(FormException, form_error_handler)
        self.add_exception_handler(ProblemDetailException, problem_detail_handler)
        add_exception_handler(self)

        @self.router.get("/", response_model=str, response_class=JSONResponse, include_in_schema=False)
        def _index() -> str:
            return "Orchestrator orchestrator"

    def instrument_app(self) -> None:
        logger.info("Activating Opentelemetry tracing to app", app=self.title)
        trace.set_tracer_provider(tracer_provider)
        FastAPIInstrumentor.instrument_app(self)
        RequestsInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()
        RedisInstrumentor().instrument()
        Psycopg2Instrumentor().instrument()
        SQLAlchemyInstrumentor().instrument(engine=db.engine, tracer_provider=tracer_provider)

    def add_sentry(
        self,
        sentry_dsn: str,
        trace_sample_rate: float,
        server_name: str,
        environment: str,
        release: Optional[str] = GIT_COMMIT_HASH,
    ) -> None:
        logger.info("Adding Sentry middleware to app", app=self.title)
        sentry_sdk.init(
            dsn=sentry_dsn,
            traces_sample_rate=trace_sample_rate,
            server_name=server_name,
            environment=environment,
            release=f"orchestrator@{release}",
            integrations=[SqlalchemyIntegration(), RedisIntegration(), FastApiIntegration(transaction_style="url")],
        )

    @staticmethod
    def register_subscription_models(product_to_subscription_model_mapping: Dict[str, Type[SubscriptionModel]]) -> None:
        """
        Register your subscription models.

        This method is needed to register your subscription models inside the orchestrator core.

        Args:
            product_to_subscription_model_mapping: The dictionary should contain a mapping of products to SubscriptionModels.
                The selection will be done depending on the name of the product.

        Returns:
            None:

        Examples:
            >>> product_to_subscription_model_mapping = { # doctest:+SKIP
            ...     "Generic Product One": GenericProductModel,
            ...     "Generic Product Two": GenericProductModel,
            ... }

        """
        SUBSCRIPTION_MODEL_REGISTRY.update(product_to_subscription_model_mapping)


main_typer_app = typer.Typer()
main_typer_app.add_typer(cli_app, name="orchestrator", help="The orchestrator CLI commands")

if __name__ == "__main__":
    main_typer_app()
