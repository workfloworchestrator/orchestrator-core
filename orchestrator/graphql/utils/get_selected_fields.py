from more_itertools import one
from strawberry.types.nodes import SelectedField, Selection

from orchestrator.graphql.types import CustomInfo


def get_selected_fields(info: CustomInfo) -> list[str]:
    """Get SelectedField names from the requested query (info).

    Can be used to get the selected fields of the schema, to only fetch those from the database.

    Args:
        - info: The info class with request information.

    returns the names of SelectedFields as a list of strings.
    """
    root_selected = info.selected_fields[0]

    def has_field_name(selection: Selection, field_name: str) -> bool:
        return isinstance(selection, SelectedField) and selection.name == field_name

    page_items = [selection for selection in root_selected.selections if has_field_name(selection, "page")]

    if not page_items:
        return [selection.name for selection in root_selected.selections if isinstance(selection, SelectedField)]

    return [selection.name for selection in one(page_items).selections if isinstance(selection, SelectedField)]
