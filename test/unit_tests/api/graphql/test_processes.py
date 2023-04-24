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

process_fields = [
    "pid",
    "workflow",
    "assignee",
    "createdBy",
    "customerId",
    "failedReason",
    "lastModifiedAt",
    "lastStatus",
    "lastStep",
    "startedAt",
    "traceback",
    "isTask",
    "productId",
]


def get_processes_query(
    first: int = 10, after: int = 0, filter_by: list[str] = None, sort_by: list[dict[str, str]] = None
) -> str:
    query = """
query Processes($first: Int!, $after: Int!, $sortBy: [Sort!], $filterBy: [[String!]!]) {
  processes(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy) {
    page {
      pid
      workflow
      assignee
      createdBy
      customerId
      failedReason
      lastModifiedAt
      lastStatus
      lastStep
      startedAt
      traceback
      isTask
      productId
    }
    pageInfo {
      totalItems
      startCursor
      hasNextPage
      endCursor
      hasPreviousPage
    }
  }
}
    """
    return json.dumps(
        {
            "operationName": "Processes",
            "query": query,
            "variables": {
                "first": first,
                "after": after,
                "sortBy": sort_by if sort_by else [],
                "filterBy": filter_by if filter_by else [],
            },
        }
    )


def test_processes_has_next_page(
    test_client, mocked_processes, mocked_processes_resumeall, generic_subscription_2, generic_subscription_1
):
    data = get_processes_query()
    response = test_client.post("/api/graphql", data=data, headers={"Content-Type": "application/json"})
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
        "totalItems": "19",
    }

    for process in processes:
        for field in process_fields:
            assert field in process


def test_process_has_previous_page(
    test_client, mocked_processes, mocked_processes_resumeall, generic_subscription_2, generic_subscription_1
):
    data = get_processes_query(after=1)
    response = test_client.post("/api/graphql", data=data, headers={"Content-Type": "application/json"})

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
        "totalItems": "19",
    }


def test_processes_sorting_asc(
    test_client, mocked_processes, mocked_processes_resumeall, generic_subscription_2, generic_subscription_1
):
    # when

    data = get_processes_query(sort_by=[{"field": "started", "order": "ASC"}])
    response = test_client.post("/api/graphql", data=data, headers={"Content-Type": "application/json"})

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
        "totalItems": "19",
    }

    assert processes[0]["startedAt"] == "2020-01-14T09:30:00+00:00"
    assert processes[1]["startedAt"] == "2020-01-14T09:30:00+00:00"
    assert processes[2]["startedAt"] == "2020-01-15T09:30:00+00:00"


def test_processes_sorting_desc(
    test_client, mocked_processes, mocked_processes_resumeall, generic_subscription_2, generic_subscription_1
):
    # when

    data = get_processes_query(sort_by=[{"field": "started", "order": "DESC"}])
    response = test_client.post("/api/graphql", data=data, headers={"Content-Type": "application/json"})

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
        "totalItems": "19",
    }

    assert processes[0]["startedAt"] == "2020-01-19T09:30:00+00:00"
    assert processes[1]["startedAt"] == "2020-01-19T09:30:00+00:00"
    assert processes[2]["startedAt"] == "2020-01-19T09:30:00+00:00"
    assert processes[3]["startedAt"] == "2020-01-19T09:30:00+00:00"
    assert processes[4]["startedAt"] == "2020-01-18T09:30:00+00:00"


def test_processes_has_filtering(
    test_client, mocked_processes, mocked_processes_resumeall, generic_subscription_2, generic_subscription_1
):
    # when

    data = get_processes_query(filter_by=[["status", "completed"]])
    response = test_client.post("/api/graphql", data=data, headers={"Content-Type": "application/json"})

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
        "totalItems": "4",
    }

    for process in processes:
        assert process["lastStatus"] == "completed"


def test_single_subscription(
    test_client, mocked_processes, mocked_processes_resumeall, generic_subscription_2, generic_subscription_1
):
    process_pid = str(mocked_processes[0])
    # when

    data = get_processes_query(filter_by=[["pid", process_pid]])
    response = test_client.post("/api/graphql", data=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    processes_data = result["data"]["processes"]
    processes = processes_data["page"]
    pageinfo = processes_data["pageInfo"]

    # then

    assert HTTPStatus.OK == response.status_code
    assert len(processes) == 1
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": "1",
    }
    assert processes[0]["pid"] == process_pid
