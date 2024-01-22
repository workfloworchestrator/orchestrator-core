from collections.abc import Callable

from more_itertools import flatten, one
from strawberry.types.nodes import FragmentSpread, InlineFragment, SelectedField, Selection

from orchestrator.graphql.types import OrchestratorInfo


def get_selected_field_selections(selected_field: Selection, name: str) -> list[Selection]:
    def is_named_field(selection: Selection, field_name: str) -> bool:
        return isinstance(selection, SelectedField) and selection.name == field_name

    page_field = [selection for selection in selected_field.selections if is_named_field(selection, name)]
    return one(page_field).selections if page_field else []


def is_query_detailed(basic_fields: tuple, type_conditions: tuple | None = None) -> Callable[[OrchestratorInfo], bool]:
    """Function wrapper that validates GraphQL queries against provided basic_fields.

    Args:
        basic_fields: tuple of the basic fields.
        type_conditions: optional tuple of the type conditions.

    Returns:
        Function that validates if a GraphQL query includes fields beyond the specified basic_fields.
    """

    def _is_model_info_detailed(info: OrchestratorInfo) -> bool:
        """Check if the query asks for detailed props."""

        def has_details(selection: Selection) -> bool:
            if isinstance(selection, InlineFragment):
                if type_conditions and selection.type_condition not in type_conditions:
                    return True
                return any(has_details(selection) for selection in selection.selections)
            if isinstance(selection, FragmentSpread):
                return any(has_details(s) for s in selection.selections)
            return selection.name not in basic_fields

        fields = flatten(
            (get_selected_field_selections(field, "page") or field.selections) for field in info.selected_fields
        )
        return any(has_details(selection) for selection in fields if selection)

    return _is_model_info_detailed


def is_querying_page_data(info: OrchestratorInfo) -> bool:
    return any(flatten(get_selected_field_selections(field, "page") for field in info.selected_fields))
