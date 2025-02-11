import strawberry
from pydantic import Field
from structlog import get_logger

from orchestrator import __version__
from orchestrator.graphql.types import OrchestratorInfo
from orchestrator.graphql.utils import create_resolver_error_handler

logger = get_logger(__name__)


VERSIONS = [f"orchestrator-core: {__version__}"]


@strawberry.type
class VersionType:
    application_versions: list[str] = Field(default=VERSIONS)


def resolve_version(info: OrchestratorInfo) -> VersionType:
    logger.debug("resolve_version() called")
    _error_handler = create_resolver_error_handler(info)

    ver = None
    try:
        ver = VersionType()
    except Exception as e:
        logger.error(f"Error getting version: {str(e)}")

    if not ver:
        _error_handler("Failed to retrieve orchestrator_core version", extensions={"code": "PACKAGE_VERSION_ERROR"})

    return VersionType(orchestrator_core=ver)
