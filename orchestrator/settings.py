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

import secrets
import string
from pathlib import Path
from typing import List, Optional

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseSettings, PostgresDsn, RedisDsn

from orchestrator.types import strEnum


class ExecutorType(strEnum):
    WORKER = "celery"
    THREADPOOL = "threadpool"


class AppSettings(BaseSettings):
    TESTING: bool = True
    SESSION_SECRET: str = "".join(secrets.choice(string.ascii_letters) for i in range(16))  # noqa: S311
    CORS_ORIGINS: str = "*"
    CORS_ALLOW_METHODS: List[str] = ["GET", "PUT", "PATCH", "POST", "DELETE", "OPTIONS", "HEAD"]
    CORS_ALLOW_HEADERS: List[str] = ["If-None-Match", "Authorization", "If-Match", "Content-Type"]
    CORS_EXPOSE_HEADERS: List[str] = [
        "Cache-Control",
        "Content-Language",
        "Content-Length",
        "Content-Type",
        "Expires",
        "Last-Modified",
        "Pragma",
        "Content-Range",
        "ETag",
    ]
    ENVIRONMENT: str = "local"
    EXECUTOR: str = ExecutorType.THREADPOOL
    WORKFLOWS_SWAGGER_HOST: str = "localhost"
    WORKFLOWS_GUI_URI: str = "http://localhost:3000"
    DATABASE_URI: PostgresDsn = "postgresql://nwa:nwa@localhost/orchestrator-core"  # type: ignore
    MAX_WORKERS: int = 5
    MAIL_SERVER: str = "localhost"
    MAIL_PORT: int = 25
    MAIL_STARTTLS: bool = False
    CACHE_URI: RedisDsn = "redis://localhost:6379/0"  # type: ignore
    CACHE_DOMAIN_MODELS: bool = False
    CACHE_HMAC_SECRET: Optional[str] = None  # HMAC signing key, used when pickling results in the cache
    ENABLE_DISTLOCK_MANAGER: bool = True
    DISTLOCK_BACKEND: str = "memory"
    CC_NOC: int = 0
    SERVICE_NAME: str = "orchestrator-core"
    LOGGING_HOST: str = "localhost"
    LOG_LEVEL: str = "DEBUG"
    SLACK_ENGINE_SETTINGS_HOOK_ENABLED: bool = False
    SLACK_ENGINE_SETTINGS_HOOK_URL: str = ""
    TRACING_ENABLED: bool = False
    TRACE_HOST: str = "http://localhost:4317"
    TRANSLATIONS_DIR: Optional[Path] = None
    WEBSOCKET_BROADCASTER_URL: str = "memory://"
    ENABLE_WEBSOCKETS: bool = True
    DISABLE_INSYNC_CHECK: bool = False
    DEFAULT_PRODUCT_WORKFLOWS: List[str] = ["modify_note"]
    SKIP_MODEL_FOR_MIGRATION_DB_DIFF: List[str] = []
    SERVE_GRAPHQL_UI: bool = True
    FEDEREATION_ENABLED: bool = False


class Oauth2Settings(BaseSettings):
    OAUTH2_ACTIVE: bool = False
    OAUTH2_RESOURCE_SERVER_ID: str = ""
    OAUTH2_RESOURCE_SERVER_SECRET: str = ""
    OAUTH2_TOKEN_URL: str = ""
    OIDC_CONF_WELL_KNOWN_URL: str = ""
    OPA_URL: str = "http://127.0.0.1:8181/v1/data/automation/authorization/allow"


app_settings = AppSettings()
oauth2_settings = Oauth2Settings()

# Tracer settings
tracer_provider = TracerProvider(resource=Resource.create({SERVICE_NAME: app_settings.SERVICE_NAME}))

otlp_exporter = OTLPSpanExporter(endpoint=app_settings.TRACE_HOST)
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
