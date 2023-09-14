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
from typing import Union

process_fields = [
    "processId",
    "isTask",
    "lastStep",
    "lastStatus",
    "assignee",
    "failedReason",
    "traceback",
    "workflowName",
    "createdBy",
    "startedAt",
    "lastModifiedAt",
    "product",
]


def get_processes_query(
    first: int = 10,
    after: int = 0,
    filter_by: Union[list[str], None] = None,
    sort_by: Union[list[dict[str, str]], None] = None,
) -> bytes:
    query = """
query ProcessQuery($first: Int!, $after: Int!, $sortBy: [GraphqlSort!], $filterBy: [GraphqlFilter!]) {
  processes(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy) {
    page {
      processId
      isTask
      lastStep
      lastStatus
      assignee
      failedReason
      traceback
      workflowName
      createdBy
      startedAt
      lastModifiedAt
      pid
      step
      status
      workflow
      started
      lastModified
      product {
        productId
        name
        description
        productType
        status
        tag
        createdAt
        endDate
      }
    }
    pageInfo {
      startCursor
      totalItems
      hasPreviousPage
      endCursor
      hasNextPage
    }
  }
}
    """
    return json.dumps(
        {
            "operationName": "ProcessQuery",
            "query": query,
            "variables": {
                "first": first,
                "after": after,
                "sortBy": sort_by if sort_by else [],
                "filterBy": filter_by if filter_by else [],
            },
        }
    ).encode("utf-8")


def get_processes_query_with_subscriptions(
    first: int = 10,
    after: int = 0,
    filter_by: Union[list[str], None] = None,
    sort_by: Union[list[dict[str, str]], None] = None,
) -> bytes:
    query = """
query ProcessQuery($first: Int!, $after: Int!, $sortBy: [GraphqlSort!], $filterBy: [GraphqlFilter!]) {
  processes(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy) {
    page {
      processId
      isTask
      lastStep
      lastStatus
      assignee
      failedReason
      traceback
      workflowName
      createdBy
      startedAt
      lastModifiedAt
      product {
        productId
        name
        description
        productType
        status
        tag
        createdAt
        endDate
      }
      subscriptions {
        page {
          description
          subscriptionId
          status
          insync
          note
          startDate
          endDate
        }
      }
    }
    pageInfo {
      startCursor
      totalItems
      hasPreviousPage
      endCursor
      hasNextPage
    }
  }
}
    """
    return json.dumps(
        {
            "operationName": "ProcessQuery",
            "query": query,
            "variables": {
                "first": first,
                "after": after,
                "sortBy": sort_by if sort_by else [],
                "filterBy": filter_by if filter_by else [],
            },
        }
    ).encode("utf-8")


def test_processes_has_next_page(
    test_client,
    mocked_processes,
    mocked_processes_resumeall,
    generic_subscription_2,
    generic_subscription_1,
):
    data = get_processes_query()
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    processes_data = result["data"]["processes"]
    processes = processes_data["page"]
    pageinfo = processes_data["pageInfo"]

    assert len(processes) == 10

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 9,
        "totalItems": 19,
    }

    for process in processes:
        for field in process_fields:
            assert field in process


def test_process_has_previous_page(
    test_client,
    mocked_processes,
    mocked_processes_resumeall,
    generic_subscription_2,
    generic_subscription_1,
):
    data = get_processes_query(after=1)
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    processes_data = result["data"]["processes"]
    processes = processes_data["page"]
    pageinfo = processes_data["pageInfo"]

    assert len(processes) == 10

    assert pageinfo == {
        "hasPreviousPage": True,
        "hasNextPage": True,
        "startCursor": 1,
        "endCursor": 10,
        "totalItems": 19,
    }


def test_processes_sorting_asc(
    test_client,
    mocked_processes,
    mocked_processes_resumeall,
    generic_subscription_2,
    generic_subscription_1,
):
    # when

    data = get_processes_query(sort_by=[{"field": "startedAt", "order": "ASC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    processes_data = result["data"]["processes"]
    processes = processes_data["page"]
    pageinfo = processes_data["pageInfo"]

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 9,
        "totalItems": 19,
    }

    assert processes[0]["startedAt"] == "2020-01-14T09:30:00+00:00"
    assert processes[1]["startedAt"] == "2020-01-14T09:30:00+00:00"
    assert processes[2]["startedAt"] == "2020-01-15T09:30:00+00:00"


def test_processes_sorting_desc(
    test_client,
    mocked_processes,
    mocked_processes_resumeall,
    generic_subscription_2,
    generic_subscription_1,
):
    # when

    data = get_processes_query(sort_by=[{"field": "startedAt", "order": "DESC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    processes_data = result["data"]["processes"]
    processes = processes_data["page"]
    pageinfo = processes_data["pageInfo"]

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 9,
        "totalItems": 19,
    }

    assert processes[0]["startedAt"] == "2020-01-19T09:30:00+00:00"
    assert processes[1]["startedAt"] == "2020-01-19T09:30:00+00:00"
    assert processes[2]["startedAt"] == "2020-01-19T09:30:00+00:00"
    assert processes[3]["startedAt"] == "2020-01-19T09:30:00+00:00"
    assert processes[4]["startedAt"] == "2020-01-18T09:30:00+00:00"


def test_processes_has_filtering(
    test_client,
    mocked_processes,
    mocked_processes_resumeall,
    generic_subscription_2,
    generic_subscription_1,
):
    # when

    data = get_processes_query(filter_by=[{"field": "lastStatus", "value": "completed"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    processes_data = result["data"]["processes"]
    processes = processes_data["page"]
    pageinfo = processes_data["pageInfo"]

    # then

    assert HTTPStatus.OK == response.status_code

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 3,
        "totalItems": 4,
    }

    for process in processes:
        assert process["lastStatus"] == "COMPLETED"


def test_processes_filtering_with_invalid_filter(
    test_client,
    mocked_processes,
    mocked_processes_resumeall,
    generic_subscription_2,
    generic_subscription_1,
):
    # when

    data = get_processes_query(
        filter_by=[{"field": "lastStatus", "value": "completed"}, {"field": "test", "value": "invalid"}]
    )
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    processes_data = result["data"]["processes"]
    errors = result["errors"]
    processes = processes_data["page"]
    pageinfo = processes_data["pageInfo"]

    assert errors == [
        {
            "message": "Invalid filter arguments",
            "path": [None, "processes", "Query"],
            "extensions": {
                "invalid_filters": [{"field": "test", "value": "invalid"}],
                "valid_filter_keys": [
                    "processId",
                    "workflowName",
                    "assignee",
                    "lastStatus",
                    "lastStep",
                    "startedAt",
                    "lastModifiedAt",
                    "failedReason",
                    "traceback",
                    "createdBy",
                    "isTask",
                    "process_id",
                    "workflow_name",
                    "last_status",
                    "last_step",
                    "started_at",
                    "last_modified_at",
                    "failed_reason",
                    "created_by",
                    "is_task",
                    "product",
                    "productTag",
                    "subscriptions",
                    "subscriptionId",
                    "subscription_id",
                    "target",
                    "organisation",
                    "istask",
                    "status",
                    "tag",
                    "creator",
                ],
            },
        }
    ]
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 3,
        "totalItems": 4,
    }

    for process in processes:
        assert process["lastStatus"] == "COMPLETED"


def test_single_process(
    test_client,
    mocked_processes,
    mocked_processes_resumeall,
    generic_subscription_2,
    generic_subscription_1,
):
    process_pid = str(mocked_processes[0])
    # when

    data = get_processes_query(filter_by=[{"field": "processId", "value": process_pid}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    processes_data = result["data"]["processes"]
    processes = processes_data["page"]
    pageinfo = processes_data["pageInfo"]

    assert len(processes) == 1
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": 1,
    }
    assert processes[0]["processId"] == process_pid


def test_single_process_with_subscriptions(
    test_client,
    mocked_processes,
    mocked_processes_resumeall,
    generic_subscription_2,
    generic_subscription_1,
):
    process_pid = str(mocked_processes[0])
    # when

    data = get_processes_query_with_subscriptions(filter_by=[{"field": "processId", "value": process_pid}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    processes_data = result["data"]["processes"]
    processes = processes_data["page"]
    pageinfo = processes_data["pageInfo"]

    assert len(processes) == 1
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": 1,
    }
    assert processes[0]["processId"] == process_pid
    assert processes[0]["subscriptions"]["page"][0]["subscriptionId"] == generic_subscription_1


def test_processes_sorting_product_tag_asc(
    test_client,
    mocked_processes,
    mocked_processes_resumeall,
    generic_subscription_2,
    generic_subscription_1,
):
    # when

    data = get_processes_query(sort_by=[{"field": "productTag", "order": "ASC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    processes_data = result["data"]["processes"]
    processes = processes_data["page"]
    pageinfo = processes_data["pageInfo"]

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 9,
        "totalItems": 15,
    }

    assert [process["product"]["tag"] for process in processes] == [
        "GEN1",
        "GEN1",
        "GEN1",
        "GEN1",
        "GEN1",
        "GEN1",
        "GEN1",
        "GEN1",
        "GEN2",
        "GEN2",
    ]
