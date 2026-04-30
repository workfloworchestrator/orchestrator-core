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

from sqlalchemy.orm import Relationship

from orchestrator.core.db.models import WorkflowTable
from orchestrator.core.graphql.utils.get_query_loaders import get_query_loaders_for_gql_fields
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
