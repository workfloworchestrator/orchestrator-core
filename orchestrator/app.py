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
from typing import Optional, Type

import sentry_sdk
import structlog
from fastapi.applications import FastAPI
from fastapi_etag.dependency import add_exception_handler
from nwastdlib.logging import initialise_logging
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse, Response

from orchestrator.api.api_v1.api import api_router
from orchestrator.api.error_handling import ProblemDetailException
from orchestrator.db import db
from orchestrator.db.database import DBSessionMiddleware
from orchestrator.exception_handlers import form_error_handler, problem_detail_handler
from orchestrator.forms import FormException
from orchestrator.settings import AppSettings, app_settings, tracer_provider
from orchestrator.version import GIT_COMMIT_HASH

logger = structlog.get_logger(__name__)


class OrchestratorCore(FastAPI):
    def __init__(  # type: ignore
        self,
        title: str = "The Orchestrator",
        description: str = "The orchestrator is a project that enables users to run workflows.",
        openapi_url: str = "/api/openapi.json",
        docs_url: str = "/api/docs",
        redoc_url: str = "/api/redoc",
        version: str = "1.0.0",
        default_response_class: Type[Response] = JSONResponse,
        base_settings: AppSettings = app_settings,
        **kwargs,
    ) -> None:
        super().__init__(
            title=title,
            description=description,
            openapi_url=openapi_url,
            docs_url=docs_url,
            redoc_url=redoc_url,
            version=version,
            default_response_class=default_response_class,
            **kwargs,
        )

        initialise_logging()

        self.include_router(api_router, prefix="/api")

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
        logger.info("Adding Sentry middelware to app", app=self.title)
        sentry_sdk.init(
            dsn=sentry_dsn,
            traces_sample_rate=trace_sample_rate,
            server_name=server_name,
            environment=environment,
            release=f"orchestrator@{release}",
            integrations=[SqlalchemyIntegration(), RedisIntegration()],
        )
        self.add_middleware(SentryAsgiMiddleware)
