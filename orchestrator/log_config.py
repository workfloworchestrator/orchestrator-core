# Copyright 2019-2024 SURF.
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
import os

from structlog import get_logger

logger = get_logger(__name__)


def logger_config(name: str, default_level: str = "INFO") -> tuple[str, dict]:
    """Create config for the given logger with the given loglevel.

    Useful for silencing noisy loggers when using LOG_LEVEL: "DEBUG" in development.

    Can be overruled at deploy time by setting an env-var, for example:
     - Level of logger "httpx" is controlled by LOG_LEVEL_HTTPX
     - Level of logger "kafka.consumer" is controlled by LOG_LEVEL_KAFKA_CONSUMER
    """
    name_upper = name.upper().replace(".", "_")
    env_var_name = f"LOG_LEVEL_{name_upper}"
    effective_level = os.environ.get(env_var_name, default_level).upper()

    # Note that by not setting a handler and using 'propagate: True', all
    # messages of sufficient level are handled (formatted) by the root logger.
    return name, {"level": effective_level, "propagate": True}


LOGGER_OVERRIDES = dict(
    [
        logger_config("asyncio"),
        logger_config("httpcore"),
    ]
)
