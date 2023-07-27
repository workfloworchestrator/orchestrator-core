from more_itertools import first
from strawberry.types.nodes import SelectedField, Selection

from orchestrator.graphql.types import OrchestratorInfo


def get_selected_fields(info: OrchestratorInfo) -> list[str]:
    """Get SelectedField names from the requested query (info).

    Can be used to get the selected fields of the schema, to only fetch those from the database.

    Args:
        info: The info class with request information.

    returns the names of SelectedFields as a list of strings.
    """
    root_selected = info.selected_fields[0]

    def has_field_name(selection: Selection, field_name: str) -> bool:
        return isinstance(selection, SelectedField) and selection.name == field_name

    page_items = first((selection for selection in root_selected.selections if has_field_name(selection, "page")), None)
    if not page_items:
        page_items = root_selected

    return [selection.name for selection in page_items.selections if isinstance(selection, SelectedField)]
