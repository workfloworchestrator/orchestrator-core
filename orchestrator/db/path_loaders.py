from typing import Iterable

import structlog
from sqlalchemy.orm import Load

from orchestrator.db.database import BaseModel as DbBaseModel
from orchestrator.db.loaders import AttrLoader, join_attr_loaders, lookup_attr_loaders

logger = structlog.get_logger(__name__)


def _split_path(query_path: str) -> Iterable[str]:
    yield from (field for field in query_path.split(".") if field != "page")


# TODO combine with the gql function which is 98% identical
def get_query_loaders_for_query_paths(query_paths: list[str], root_model: type[DbBaseModel]) -> list[Load]:
    """Get sqlalchemy query loaders for the given paths."""
    # Strip page and sort by length to find the longest match first
    # query_paths = [path.removeprefix("page.") for path in get_selected_paths(info)]
    query_paths.sort(key=lambda x: x.count("."), reverse=True)

    def get_loader_for_path(query_path: str) -> tuple[str, Load | None]:
        next_model = root_model

        matched_fields: list[str] = []
        path_loaders: list[AttrLoader] = []

        for field in _split_path(query_path):
            if not (attr_loaders := lookup_attr_loaders(next_model, field)):
                break

            matched_fields.append(field)
            path_loaders.extend(attr_loaders)
            next_model = attr_loaders[-1].next_model

        return ".".join(matched_fields), join_attr_loaders(path_loaders)

    query_loaders: dict[str, Load] = {}

    for path in query_paths:
        matched_path, loader = get_loader_for_path(path)
        if not matched_path or not loader or matched_path in query_loaders:
            continue
        if any(known_path.startswith(f"{matched_path}.") for known_path in query_loaders):
            continue
        query_loaders[matched_path] = loader

    loaders = list(query_loaders.values())
    logger.debug(
        "Generated query loaders for paths",
        root_model=root_model,
        query_paths=query_paths,
        query_loaders=[str(i.path) for i in loaders],
    )
    return loaders
