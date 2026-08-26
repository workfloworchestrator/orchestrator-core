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

from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_utils import Ltree

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.schemas.search_requests import SearchRequest
from orchestrator.core.search.aggregations import AggregationType
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.filters import FilterCondition, FilterTree, LtreeFilter, PathFilter
from orchestrator.core.search.filters.definitions import operators_for
from orchestrator.core.search.query.exceptions import (
    EmptyFilterPathError,
    IncompatibleAggregationTypeError,
    IncompatibleFilterTypeError,
    IncompatibleTemporalGroupingTypeError,
    InvalidEntityPrefixError,
    InvalidLtreePatternError,
    PathNotFoundError,
)
from orchestrator.core.search.query.mixins import OrderBy


def is_filter_compatible_with_field_type(filter_condition: FilterCondition, field_type: FieldType) -> bool:
    """Check whether a filter condition is compatible with a given field type.

    Args:
        filter_condition (FilterCondition): The filter condition instance to check.
        field_type (FieldType): The type of field from the index schema.

    Returns:
        bool: True if the filter condition is valid for the given field type, False otherwise.
    """

    # LtreeFilter is for path filtering only and is thus compatible with all field types.
    if isinstance(filter_condition, LtreeFilter):
        return True

    # Get valid operators for this field type and check if the filter's operator is valid.
    valid_operators = operators_for(field_type)
    return filter_condition.op in valid_operators


async def is_lquery_syntactically_valid(pattern: str, db_session: AsyncSession) -> bool:
    """Validate whether a string is a syntactically correct `lquery` pattern.

    Args:
        pattern (str): The LTree lquery pattern string to validate.
        db_session (AsyncSession): The database session used to test casting.

    Returns:
        bool: True if the pattern is valid, False if it fails to cast in PostgreSQL.
    """

    try:
        async with db_session.begin_nested():
            await db_session.execute(text("SELECT CAST(:pattern AS lquery)"), {"pattern": pattern})
        return True
    except ProgrammingError:
        return False


async def get_structured_filter_schema(session: AsyncSession) -> dict[str, str]:
    """Retrieve all distinct filterable paths and their field types from the index.

    Args:
        session: Async database session

    Returns:
        Dict[str, str]: Mapping of path strings to their corresponding field type values.
    """

    stmt = select(AiSearchIndex.path, AiSearchIndex.value_type).distinct().order_by(AiSearchIndex.path)
    result = await session.execute(stmt)
    return {str(path): value_type.value for path, value_type in result}


async def validate_filter_path(path: str, session: AsyncSession) -> str | None:
    """Check if a given path exists in the index and return its field type.

    Args:
        path (str): The fully qualified LTree path.
        session: Async database session

    Returns:
        Optional[str]: The value type of the field if found, otherwise None.
    """

    stmt = select(AiSearchIndex.value_type).where(AiSearchIndex.path == Ltree(path)).limit(1)
    result = await session.execute(stmt)
    scalar = result.scalar_one_or_none()
    return scalar.value if scalar else None


async def complete_filter_validation(filter: PathFilter, entity_type: EntityType, session: AsyncSession) -> None:
    """Validate a PathFilter against the database schema and entity type.

    Checks performed:
    1. LTree filter syntax (for LtreeFilter only)
    2. Non-empty path
    3. Path exists in the database schema
    4. Filter type matches the field's value_type
    5. Path starts with the correct entity type prefix (unless wildcard)

    Args:
        filter (PathFilter): The filter to validate.
        entity_type (EntityType): The entity type being searched.
        session: Async database session

    Raises:
        ValueError: If any of the validation checks fail.
    """

    # Ltree is a special case
    if isinstance(filter.condition, LtreeFilter):
        lquery_pattern = filter.condition.value
        if not await is_lquery_syntactically_valid(lquery_pattern, session):
            raise InvalidLtreePatternError(lquery_pattern)
        return

    if not filter.path or not filter.path.strip():
        raise EmptyFilterPathError()

    # 1. Check if path exists in database
    db_field_type_str = await validate_filter_path(filter.path, session)
    if db_field_type_str is None:
        raise PathNotFoundError(filter.path)

    db_field_type = FieldType(db_field_type_str)

    # 2. Check filter compatibility with field type
    if not is_filter_compatible_with_field_type(filter.condition, db_field_type):
        expected_operators = operators_for(db_field_type)
        raise IncompatibleFilterTypeError(
            filter.condition.op.value, db_field_type.value, filter.path, expected_operators
        )

    # 3. Check entity type prefix requirements (unless it's a wildcard path)
    expected_prefix = f"{entity_type.value.lower()}."
    if not filter.path.startswith(expected_prefix) and not filter.path.startswith("*"):
        raise InvalidEntityPrefixError(filter.path, expected_prefix, entity_type.value)


async def validate_filter_tree(filters: FilterTree | None, entity_type: EntityType, session: AsyncSession) -> None:
    """Validate all PathFilter leaves in a FilterTree."""
    if filters is None:
        return
    for leaf in filters.get_all_leaves():
        await complete_filter_validation(leaf, entity_type, session)


async def validate_aggregation_field(agg_type: AggregationType, field_path: str, session: AsyncSession) -> None:
    """Validate that an aggregation field exists and is compatible with the aggregation type.

    Note: Only for FieldAggregations (SUM, AVG, MIN, MAX). COUNT does not require field validation.

    Args:
        agg_type: The aggregation type enum
        field_path: The field path to validate
        session: Async database session

    Raises:
        PathNotFoundError: If the field doesn't exist in the database.
        IncompatibleAggregationTypeError: If the field type is incompatible with the aggregation type.
    """
    # Check if field exists in database
    field_type_str = await validate_filter_path(field_path, session)
    if field_type_str is None:
        raise PathNotFoundError(field_path)

    # Validate field type compatibility with aggregation type
    if agg_type in (AggregationType.SUM, AggregationType.AVG):
        if field_type_str not in (FieldType.INTEGER.value, FieldType.FLOAT.value):
            raise IncompatibleAggregationTypeError(
                agg_type.value, field_type_str, field_path, [FieldType.INTEGER.value, FieldType.FLOAT.value]
            )
    elif agg_type in (AggregationType.MIN, AggregationType.MAX):
        if field_type_str not in (FieldType.INTEGER.value, FieldType.FLOAT.value, FieldType.DATETIME.value):
            raise IncompatibleAggregationTypeError(
                agg_type.value,
                field_type_str,
                field_path,
                [FieldType.INTEGER.value, FieldType.FLOAT.value, FieldType.DATETIME.value],
            )


async def validate_temporal_grouping_field(field_path: str, session: AsyncSession) -> None:
    """Validate that a field exists and is a datetime type for temporal grouping.

    Args:
        field_path: The field path to validate
        session: Async database session

    Raises:
        PathNotFoundError: If the field doesn't exist in the database
        IncompatibleTemporalGroupingTypeError: If the field is not a datetime type
    """
    # Check if field exists in database
    field_type_str = await validate_filter_path(field_path, session)
    if field_type_str is None:
        raise PathNotFoundError(field_path)

    # Validate field type is datetime
    if field_type_str != FieldType.DATETIME.value:
        raise IncompatibleTemporalGroupingTypeError(field_path, field_type_str)


async def validate_grouping_fields(group_by_paths: list[str], session: AsyncSession) -> None:
    """Validate that all grouping field paths exist in the database.

    Args:
        group_by_paths: List of field paths to group by
        session: Async database session

    Raises:
        PathNotFoundError: If any path doesn't exist in the database
    """
    for path in group_by_paths:
        field_type = await validate_filter_path(path, session)
        if field_type is None:
            raise PathNotFoundError(path)


async def validate_order_by_fields(order_by: list[OrderBy] | None, session: AsyncSession) -> None:
    """Validate that order_by field paths exist in the database.

    Args:
        order_by: List of ordering instructions, or None
        session: Async database session

    Raises:
        PathNotFoundError: If a field path doesn't exist in the database

    Note:
        Only validates fields that appear to be paths (contain dots).
        Aggregation aliases (no dots, like 'count') are skipped as they
        cannot be validated until query execution time.
    """
    if order_by is None:
        return

    for order_instr in order_by:
        # Skip aggregation aliases (no dots, e.g., 'count', 'revenue')
        if "." not in order_instr.field:
            continue

        field_type = await validate_filter_path(order_instr.field, session)
        if field_type is None:
            raise PathNotFoundError(order_instr.field)


async def get_ai_search_index_by_entity_type_and_path(
    entity_type: EntityType, path: str, session: AsyncSession
) -> AiSearchIndex | None:
    stmt = (
        select(AiSearchIndex)
        .where(AiSearchIndex.path == Ltree(path), AiSearchIndex.entity_type == entity_type.value)
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def validate_structured_order_by_element(
    entity_type: EntityType | None, request: SearchRequest | None, session: AsyncSession
) -> None:
    if request and request.order_by and entity_type:
        element = request.order_by.element
        exists = await get_ai_search_index_by_entity_type_and_path(entity_type, element, session)
        if not exists:
            raise ValueError(f"Element {element} is not a valid path")
