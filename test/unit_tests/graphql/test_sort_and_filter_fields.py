# Copyright 2022 SURF.
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
import json
from http import HTTPStatus

import pytest

from orchestrator.db.filters.process import process_filter_fields
from orchestrator.db.filters.product import product_filter_fields
from orchestrator.db.filters.product_block import product_block_filter_fields
from orchestrator.db.filters.resource_type import resource_type_filter_fields
from orchestrator.db.filters.subscription import subscription_filter_fields
from orchestrator.db.filters.workflow import workflow_filter_fields
from orchestrator.db.sorting.process import process_sort_fields
from orchestrator.db.sorting.product import product_sort_fields
from orchestrator.db.sorting.product_block import product_block_sort_fields
from orchestrator.db.sorting.resource_type import resource_type_sort_fields
from orchestrator.db.sorting.subscription import subscription_sort_fields
from orchestrator.db.sorting.workflow import workflow_sort_fields


def get_page_info_sort_and_filter_fields(type_name) -> bytes:
    query = f"""
query PageInfoSortAndFilterQuery {{
  {type_name} {{
    pageInfo {{
      sortFields
      filterFields
    }}
  }}
}}
"""
    return json.dumps(
        {
            "operationName": "PageInfoSortAndFilterQuery",
            "query": query,
        }
    ).encode("utf-8")


@pytest.mark.parametrize(
    "type_name, sort_fields, filter_fields",
    [
        ("processes", process_sort_fields(), process_filter_fields()),
        ("subscriptions", subscription_sort_fields(), subscription_filter_fields()),
        ("products", product_sort_fields(), product_filter_fields()),
        ("productBlocks", product_block_sort_fields(), product_block_filter_fields()),
        ("workflows", workflow_sort_fields(), workflow_filter_fields()),
        ("resourceTypes", resource_type_sort_fields(), resource_type_filter_fields()),
    ],
)
def test_process_sort_and_filter_fields_in_page_info(test_client, type_name, sort_fields, filter_fields):
    data = get_page_info_sort_and_filter_fields(type_name)
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    processes_data = result["data"][type_name]
    pageinfo = processes_data["pageInfo"]

    assert pageinfo == {
        "sortFields": sort_fields,
        "filterFields": filter_fields,
    }
