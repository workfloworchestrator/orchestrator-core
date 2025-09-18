from typing import List, Tuple

from orchestrator.search.core.types import ExtractedField, FieldType


def fields(field_data: List[Tuple[str, str, FieldType]]) -> List[ExtractedField]:
    """Create a list of ExtractedFields from a list of (path, value, field_type) tuples."""
    return [ExtractedField(path, value, field_type) for path, value, field_type in field_data]
