from typing import assert_never

from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy_utils import Ltree

from orchestrator.db import db
from orchestrator.db.database import WrappedSession
from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.types import EntityType, FieldType
from orchestrator.search.filters import (
    DateRangeFilter,
    DateValueFilter,
    EqualityFilter,
    FilterCondition,
    FilterTree,
    LtreeFilter,
    NumericRangeFilter,
    NumericValueFilter,
    PathFilter,
    StringFilter,
)


def is_filter_compatible_with_field_type(filter_condition: FilterCondition, field_type: FieldType) -> bool:
    """Check whether a filter condition is compatible with a given field type.

    Parameters
    ----------
    filter_condition : FilterCondition
        The filter condition instance to check.
    field_type : FieldType
        The type of field from the index schema.

    Returns:
    -------
    bool
        True if the filter condition is valid for the given field type, False otherwise.
    """

    match filter_condition:
        case LtreeFilter():
            return True  # Filters for path only
        case DateRangeFilter() | DateValueFilter():
            return field_type == FieldType.DATETIME
        case NumericRangeFilter() | NumericValueFilter():
            return field_type in {FieldType.INTEGER, FieldType.FLOAT}
        case StringFilter():
            return field_type == FieldType.STRING
        case EqualityFilter():
            return field_type in {
                FieldType.BOOLEAN,
                FieldType.UUID,
                FieldType.BLOCK,
                FieldType.RESOURCE_TYPE,
                FieldType.STRING,
            }
        case _:
            assert_never(filter_condition)


def is_lquery_syntactically_valid(pattern: str, db_session: WrappedSession) -> bool:
    """Validate whether a string is a syntactically correct `lquery` pattern.

    Parameters
    ----------
    pattern : str
        The LTree lquery pattern string to validate.
    db_session : WrappedSession
        The database session used to test casting.

    Returns:
    -------
    bool
        True if the pattern is valid, False if it fails to cast in PostgreSQL.
    """
    try:
        with db_session.begin_nested():
            db_session.execute(text("SELECT CAST(:pattern AS lquery)"), {"pattern": pattern})
        return True
    except ProgrammingError:
        return False


def get_structured_filter_schema() -> dict[str, str]:
    """Retrieve all distinct filterable paths and their field types from the index.

    Returns:
    -------
    Dict[str, str]
        Mapping of path strings to their corresponding field type values.
    """
    stmt = select(AiSearchIndex.path, AiSearchIndex.value_type).distinct().order_by(AiSearchIndex.path)
    result = db.session.execute(stmt)
    return {str(path): value_type.value for path, value_type in result}


def validate_filter_path(path: str) -> str | None:
    """Check if a given path exists in the index and return its field type.

    Parameters
    ----------
    path : str
        The fully qualified LTree path.

    Returns:
    -------
    Optional[str]
        The value type of the field if found, otherwise None.
    """
    stmt = select(AiSearchIndex.value_type).where(AiSearchIndex.path == Ltree(path)).limit(1)
    result = db.session.execute(stmt).scalar_one_or_none()
    return result.value if result else None


async def complete_filter_validation(filter: PathFilter, entity_type: EntityType) -> None:
    """Validate a PathFilter against the database schema and entity type.

    Checks performed:
    1. LTree filter syntax (for LtreeFilter only)
    2. Non-empty path
    3. Path exists in the database schema
    4. Filter type matches the field's value_type
    5. Path starts with the correct entity type prefix (unless wildcard)

    Parameters
    ----------
    filter : PathFilter
        The filter to validate.
    entity_type : EntityType
        The entity type being searched.

    Raises:
    ------
    ValueError
        If any of the validation checks fail.
    """
    # Ltree is a special case
    if isinstance(filter.condition, LtreeFilter):
        lquery_pattern = filter.condition.value
        if not is_lquery_syntactically_valid(lquery_pattern, db.session):
            raise ValueError(f"Ltree pattern '{lquery_pattern}' has invalid syntax.")
        return

    if not filter.path or not filter.path.strip():
        raise ValueError("Filter path cannot be empty")

    # 1. Check if path exists in database
    db_field_type_str = validate_filter_path(filter.path)
    if db_field_type_str is None:
        raise ValueError(f"Path '{filter.path}' does not exist in database schema")

    db_field_type = FieldType(db_field_type_str)

    # 2. Check filter compatibility with field type
    if not is_filter_compatible_with_field_type(filter.condition, db_field_type):
        raise ValueError(
            f"Filter '{type(filter.condition).__name__}' not compatible with field type '{db_field_type.value}'"
        )

    # 3. Check entity type prefix requirements (unless it's a wildcard path)
    expected_prefix = f"{entity_type.value.lower()}."
    if not filter.path.startswith(expected_prefix) and not filter.path.startswith("*"):
        raise ValueError(
            f"Filter path '{filter.path}' must start with '{expected_prefix}' for {entity_type.value} searches."
        )


async def validate_filter_tree(filters: FilterTree | None, entity_type: EntityType) -> None:
    """Validate all PathFilter leaves in a FilterTree."""
    if filters is None:
        return
    for leaf in filters.get_all_leaves():
        await complete_filter_validation(leaf, entity_type)
