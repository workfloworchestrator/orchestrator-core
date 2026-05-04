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

from structlog import get_logger

from orchestrator.core import __version__
from orchestrator.core.graphql.resolvers.helpers import make_async
from orchestrator.core.graphql.schemas.version import VersionType
from orchestrator.core.graphql.types import OrchestratorInfo
from orchestrator.core.graphql.utils import create_resolver_error_handler

logger = get_logger(__name__)


VERSIONS = [f"orchestrator-core: {__version__}"]


@make_async
def resolve_version(info: OrchestratorInfo) -> VersionType | None:
    logger.debug("resolve_version() called")
    _error_handler = create_resolver_error_handler(info)

    ver = None
    try:
        ver = VersionType(application_versions=VERSIONS)
    except Exception as e:
        logger.error(f"Error getting version: {str(e)}")
        _error_handler("Failed to retrieve orchestrator_core version", extensions={"code": "PACKAGE_VERSION_ERROR"})

    return ver
