# Copyright 2019-2026 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest import mock

from orchestrator.core.graphql.utils.get_selected_paths import get_selected_paths
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
