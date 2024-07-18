from typing import Iterable

from graphql.pyutils import camel_to_snake
from more_itertools import unique_everseen
from strawberry.types.nodes import FragmentSpread, InlineFragment, SelectedField

from orchestrator.graphql.types import OrchestratorInfo


def _get_fields(elem: InlineFragment | FragmentSpread | SelectedField, *field_names: str) -> Iterable[str]:
    if not elem.selections:
        yield ".".join(field_names)
        return

    for selection in elem.selections:
        match selection:
            case InlineFragment() | FragmentSpread():
                yield from _get_fields(selection, *field_names)
            case SelectedField(name=field_name):
                yield from _get_fields(selection, *field_names, camel_to_snake(field_name))


def get_selected_paths(info: OrchestratorInfo) -> list[str]:
    """Get all selected paths in the GraphQL query.

    Example:
        ['page.name',
         'page.target',
         'page.products.tag',
         'page.products.product_blocks.name',
         'page.products.product_blocks.resource_types.description',
         'page.products.product_blocks.in_use_by.name',
         'page.created_at'
        ]
    """

    def get_all_paths() -> Iterable[str]:
        for selected_field in info.selected_fields:
            yield from _get_fields(selected_field)

    return list(unique_everseen(get_all_paths()))
