import strawberry

from orchestrator import __version__

VERSIONS = [f"orchestrator-core: {__version__}"]


@strawberry.type
class VersionType:
    application_versions: list[str]
