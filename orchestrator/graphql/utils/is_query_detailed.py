from typing import Callable

from more_itertools import flatten, one
from strawberry.types.nodes import FragmentSpread, InlineFragment, SelectedField, Selection

from orchestrator.graphql.types import OrchestratorInfo


def get_selections(selected_field: Selection) -> list[Selection]:
    def has_field_name(selection: Selection, field_name: str) -> bool:
        return isinstance(selection, SelectedField) and selection.name == field_name

    page_field = [selection for selection in selected_field.selections if has_field_name(selection, "page")]

    if not page_field:
        return selected_field.selections
    return one(page_field).selections


def is_query_detailed(basic_fields: tuple) -> Callable[[OrchestratorInfo], bool]:
    """Function wrapper that validates GraphQL queries against provided basic_fields.

    Args:
        basic_fields: tuple of the basic fields.

    Returns:
        Function that validates if a GraphQL query includes fields beyond the specified basic_fields.
    """

    def _is_model_info_detailed(info: OrchestratorInfo) -> bool:
        """Check if the query asks for detailed props."""

        def has_details(selection: Selection) -> bool:
            if isinstance(selection, InlineFragment):
                return any(has_details(selection) for selection in selection.selections)
            if isinstance(selection, FragmentSpread):
                return any(has_details(s) for s in selection.selections)
            return selection.name not in basic_fields

        fields = flatten(get_selections(field) for field in info.selected_fields)
        return any(has_details(selection) for selection in fields if selection)

    return _is_model_info_detailed
