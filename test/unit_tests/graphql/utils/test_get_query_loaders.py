from unittest import mock

from sqlalchemy.orm import Relationship

from orchestrator.db.models import WorkflowTable
from orchestrator.graphql.utils.get_query_loaders import get_query_loaders_for_gql_fields
from test.unit_tests.graphql.utils.fixtures import LARGE_QUERY_SELECTED_FIELDS, SMALL_QUERY_SELECTED_FIELDS


def to_string(loader) -> list[str]:
    # Make loader human readable by str-formatting the Model relations that it joins
    return [str(elem) for elem in loader.path.path if isinstance(elem, Relationship)]


def test_get_query_loaders():
    # given
    mock_info = mock.Mock()
    mock_info.selected_fields = LARGE_QUERY_SELECTED_FIELDS

    # when
    query_loaders = get_query_loaders_for_gql_fields(WorkflowTable, mock_info)

    # then
    actual_loaders = [to_string(loader) for loader in query_loaders]
    expected_loaders = [
        [
            "WorkflowTable.products",
            "ProductTable.product_blocks",
            "ProductBlockTable.resource_types",
            "ResourceTypeTable.product_blocks",
        ],
        [
            "WorkflowTable.products",
            "ProductTable.product_blocks",
            "ProductBlockTable.in_use_by_block_relations",
            "ProductBlockRelationTable.in_use_by",
        ],
    ]

    assert sorted(actual_loaders) == sorted(expected_loaders)


def test_get_query_loaders_noop():
    # given
    mock_info = mock.Mock()
    mock_info.selected_fields = SMALL_QUERY_SELECTED_FIELDS

    # when
    query_loaders = get_query_loaders_for_gql_fields(WorkflowTable, mock_info)

    # then
    actual_loaders = [to_string(loader) for loader in query_loaders]
    expected_loaders = []

    assert sorted(actual_loaders) == sorted(expected_loaders)
