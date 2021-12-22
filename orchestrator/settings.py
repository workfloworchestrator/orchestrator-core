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

from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseSettings


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
    WORKFLOWS_SWAGGER_HOST: str = "localhost"
    WORKFLOWS_GUI_URI: str = "http://localhost:3000"
    DATABASE_URI: str = "postgresql://nwa:nwa@localhost/orchestrator-core"
    MAX_WORKERS: int = 5
    MAIL_SERVER: str = "localhost"
    MAIL_PORT: int = 25
    MAIL_STARTTLS: bool = False
    CACHE_HOST: str = "127.0.0.1"
    CACHE_PORT: int = 6379
    CC_NOC: int = 0
    SERVICE_NAME: str = "orchestrator-core"
    LOGGING_HOST: str = "localhost"
    LOG_LEVEL: str = "DEBUG"
    SLACK_ENGINE_SETTINGS_HOOK_ENABLED: bool = False
    SLACK_ENGINE_SETTINGS_HOOK_URL: str = ""
    TRACING_ENABLED: bool = False
    TRANSLATIONS_DIR: Optional[Path] = None
    WEBSOCKET_BROADCASTER_URL: str = "memory://"
    ENABLE_WEBSOCKETS: bool = True


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
tracer_provider = TracerProvider()

jaeger_exporter = JaegerExporter(agent_host_name=app_settings.LOGGING_HOST, udp_split_oversized_batches=True)
tracer_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
