from typing import Sequence

import structlog
from sqlalchemy.orm import Load

from orchestrator.db.database import BaseModel as DbBaseModel
from orchestrator.db.loaders import (
    get_query_loaders_for_model_paths,
)
from orchestrator.graphql.types import OrchestratorInfo
from orchestrator.graphql.utils.get_selected_paths import get_selected_paths

logger = structlog.get_logger(__name__)


def get_query_loaders_for_gql_fields(
    root_model: type[DbBaseModel], info: OrchestratorInfo, exclude_paths: Sequence[str] | None = None
) -> list[Load]:
    """Get sqlalchemy query loaders for the given GraphQL query.

    Based on the GraphQL query's selected fields, returns the required DB loaders to use
    in SQLALchemy's `.options()` for efficiently quering (nested) relationships.
    """
    model_paths = [path.removeprefix("page.") for path in get_selected_paths(info)]
    logger.info("### SELECTED PATHS", model_paths=model_paths)

    if exclude_paths:
        model_paths = [path for path in model_paths if not any(path.startswith(excluded) for excluded in exclude_paths)]

    return get_query_loaders_for_model_paths(root_model, model_paths)
