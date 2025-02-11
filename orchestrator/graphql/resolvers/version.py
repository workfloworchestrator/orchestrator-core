import strawberry
from orchestrator.graphql.types import OrchestratorInfo
from orchestrator.graphql.utils import create_resolver_error_handler
from structlog import get_logger
from importlib.metadata import version, PackageNotFoundError


logger = get_logger(__name__)


@strawberry.type
class VersionType:
    orchestrator_core: str


def resolve_version(info: OrchestratorInfo) -> VersionType:
    logger.debug("resolve_version() called")
    _error_handler = create_resolver_error_handler(info)

    ver = None
    try:
        ver = version("orchestrator-core")
    except PackageNotFoundError:
        logger.error("orchestrator-core package not found")
    except Exception as e:
        logger.error(f"Error getting orchestrator-core version: {str(e)}")

    if not ver:
        _error_handler("Failed to retrieve orchestrator_core version", extensions={"code": "PACKAGE_VERSION_ERROR"})

    return VersionType(orchestrator_core=ver)
