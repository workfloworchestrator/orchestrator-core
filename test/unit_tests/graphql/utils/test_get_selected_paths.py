from unittest import mock

from orchestrator.graphql.utils.get_selected_paths import get_selected_paths
from test.unit_tests.graphql.utils.fixtures import LARGE_QUERY_SELECTED_FIELDS, SMALL_QUERY_SELECTED_FIELDS


def test_get_selected_paths_large():
    mock_info = mock.Mock()
    mock_info.selected_fields = LARGE_QUERY_SELECTED_FIELDS
    paths = get_selected_paths(mock_info)

    assert sorted(paths) == sorted(
        [
            "page.name",
            "page.target",
            "page.products.tag",
            "page.products.product_blocks.name",
            "page.products.product_blocks.resource_types.description",
            "page.products.product_blocks.resource_types.product_blocks.name",
            "page.products.product_blocks.in_use_by.name",
            "page.created_at",
        ]
    )


def test_get_selected_paths_empty():
    # given
    mock_info = mock.Mock()
    mock_info.selected_fields = []

    # when
    paths = get_selected_paths(mock_info)

    # then
    assert paths == []


def test_get_selected_paths_one():
    # given
    mock_info = mock.Mock()
    mock_info.selected_fields = SMALL_QUERY_SELECTED_FIELDS

    # when
    paths = get_selected_paths(mock_info)

    # then
    assert paths == [
        "page.created_at",
    ]
