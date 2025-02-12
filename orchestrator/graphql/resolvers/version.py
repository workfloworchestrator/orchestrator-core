from structlog import get_logger

from orchestrator import __version__
from orchestrator.graphql.schemas.version import VersionType
from orchestrator.graphql.types import OrchestratorInfo
from orchestrator.graphql.utils import create_resolver_error_handler

logger = get_logger(__name__)


VERSIONS = [f"orchestrator-core: {__version__}"]


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
