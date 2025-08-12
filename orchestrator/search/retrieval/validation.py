from typing import Dict, Optional
from sqlalchemy import select
from sqlalchemy_utils import Ltree
from orchestrator.db import db
from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.types import FieldType, EntityKind
from orchestrator.search.filters import (
    PathFilter,
    FilterCondition,
    StringFilter,
    EqualityFilter,
    DateValueFilter,
    DateRangeFilter,
    LtreeFilter,
    NumericRangeFilter,
    NumericValueFilter,
)

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError


def is_filter_compatible_with_field_type(filter_condition: FilterCondition, field_type: FieldType) -> bool:
    """Check if a filter condition is compatible with a field type."""

    if isinstance(filter_condition, LtreeFilter):
        return True  # Filters for path only
    elif isinstance(filter_condition, (DateRangeFilter, DateValueFilter)):
        return field_type == FieldType.DATETIME
    elif isinstance(filter_condition, (NumericRangeFilter, NumericValueFilter)):
        return field_type in {FieldType.INTEGER, FieldType.FLOAT}
    elif isinstance(filter_condition, StringFilter):
        return field_type == FieldType.STRING
    elif isinstance(filter_condition, EqualityFilter):
        return field_type in {FieldType.BOOLEAN, FieldType.UUID, FieldType.BLOCK, FieldType.RESOURCE_TYPE}

    return False


def is_lquery_syntactically_valid(pattern: str, db_session) -> bool:
    """
    Checks if a string is a syntactically valid lquery pattern by attempting to cast it in the database.
    """
    try:
        with db_session.begin_nested():
            db_session.execute(text("SELECT CAST(:pattern AS lquery)"), {"pattern": pattern})
        return True
    except ProgrammingError:
        return False


def get_structured_filter_schema() -> Dict[str, str]:
    """
    Queries the index for all distinct paths with value_type.
    """
    stmt = select(AiSearchIndex.path, AiSearchIndex.value_type).distinct().order_by(AiSearchIndex.path)
    result = db.session.execute(stmt)
    return {str(path): value_type.value for path, value_type in result}


def validate_filter_path(path: str) -> Optional[str]:
    """
    Checks if a given path exists in the index and returns its type
    using the AiSearchIndex ORM model.
    """
    stmt = select(AiSearchIndex.value_type).where(AiSearchIndex.path == Ltree(path)).limit(1)
    result = db.session.execute(stmt).scalar_one_or_none()
    return result.value if result else None


async def complete_filter_validation(filter: PathFilter, entity_type: EntityKind) -> None:
    """
    Validates a filter against the database schema.

    Checks:
    1. Path exists in the database (skip for LtreeFilter)
    2. Filter type is compatible with the field's value_type
    3. Path follows entity type prefix requirements

    Args:
        filter: The PathFilter to validate
        entity_type: The entity type being searched

    Raises:
        ValueError: If validation fails
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
