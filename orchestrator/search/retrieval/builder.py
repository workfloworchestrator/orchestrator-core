# Copyright 2019-2025 SURF, GÉANT.
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

from collections import defaultdict
from typing import Sequence

from sqlalchemy import Select, String, cast, func, select
from sqlalchemy.engine import Row

from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.types import EntityType, FieldType, FilterOp, UIType
from orchestrator.search.filters import LtreeFilter
from orchestrator.search.schemas.parameters import BaseSearchParameters
from orchestrator.search.schemas.results import ComponentInfo, LeafInfo


def create_path_autocomplete_lquery(prefix: str) -> str:
    """Create the lquery pattern for a multi-level path autocomplete search."""
    return f"{prefix}*.*"


def build_candidate_query(params: BaseSearchParameters) -> Select:
    """Build the base query for retrieving candidate entities.

    Constructs a `SELECT` statement that retrieves distinct `entity_id` values
    from the index table for the given entity type, applying any structured
    filters from the provided search parameters.

    Args:
        params (BaseSearchParameters): The search parameters containing the entity type and optional filters.

    Returns:
        Select: The SQLAlchemy `Select` object representing the query.
    """

    stmt = select(AiSearchIndex.entity_id).where(AiSearchIndex.entity_type == params.entity_type.value).distinct()

    if params.filters is not None:
        entity_id_col = AiSearchIndex.entity_id
        stmt = stmt.where(
            params.filters.to_expression(
                entity_id_col,
                entity_type_value=params.entity_type.value,
            )
        )

    return stmt


def build_paths_query(entity_type: EntityType, prefix: str | None = None, q: str | None = None) -> Select:
    """Build the query for retrieving paths and their value types for leaves/components processing."""
    stmt = select(AiSearchIndex.path, AiSearchIndex.value_type).where(AiSearchIndex.entity_type == entity_type.value)

    if prefix:
        lquery_pattern = create_path_autocomplete_lquery(prefix)
        ltree_filter = LtreeFilter(op=FilterOp.MATCHES_LQUERY, value=lquery_pattern)
        stmt = stmt.where(ltree_filter.to_expression(AiSearchIndex.path, path=""))

    stmt = stmt.group_by(AiSearchIndex.path, AiSearchIndex.value_type)

    if q:
        score = func.similarity(cast(AiSearchIndex.path, String), q)
        stmt = stmt.order_by(score.desc(), AiSearchIndex.path)
    else:
        stmt = stmt.order_by(AiSearchIndex.path)

    return stmt


def process_path_rows(rows: Sequence[Row]) -> tuple[list[LeafInfo], list[ComponentInfo]]:
    """Process query results to extract leaves and components information.

    Parameters
    ----------
    rows : Sequence[Row]
        Database rows containing path and value_type information

    Returns:
    -------
    tuple[list[LeafInfo], list[ComponentInfo]]
        Processed leaves and components
    """
    leaves_dict: dict[str, set[UIType]] = defaultdict(set)
    leaves_paths_dict: dict[str, set[str]] = defaultdict(set)
    components_set: set[str] = set()

    for row in rows:
        path, value_type = row

        path_str = str(path)
        path_segments = path_str.split(".")

        # Remove numeric segments
        clean_segments = [seg for seg in path_segments if not seg.isdigit()]

        if clean_segments:
            # Last segment is a leaf
            leaf_name = clean_segments[-1]
            ui_type = UIType.from_field_type(FieldType(value_type))
            leaves_dict[leaf_name].add(ui_type)
            leaves_paths_dict[leaf_name].add(path_str)

            # All segments except the first/last are components
            for component in clean_segments[1:-1]:
                components_set.add(component)

    leaves = [
        LeafInfo(name=leaf, ui_types=list(types), paths=sorted(leaves_paths_dict[leaf]))
        for leaf, types in leaves_dict.items()
    ]
    components = [ComponentInfo(name=component, ui_types=[UIType.COMPONENT]) for component in sorted(components_set)]

    return leaves, components
