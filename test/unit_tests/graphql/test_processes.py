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
from unittest.mock import patch

import pytest

from orchestrator import app_settings
from test.unit_tests.fixtures.workflows import add_soft_deleted_workflows  # noqa: F401


@pytest.fixture(autouse=True)
def _add_soft_deleted_workflows(add_soft_deleted_workflows):  # noqa: F811
    add_soft_deleted_workflows(10)


process_fields = [
    "processId",
    "isTask",
    "lastStep",
    "lastStatus",
    "assignee",
    "failedReason",
    "traceback",
    "workflowId",
    "workflowName",
    "createdBy",
    "startedAt",
    "lastModifiedAt",
    "product",
]


def get_processes_query(
    first: int = 10,
    after: int = 0,
    filter_by: list[dict[str, str]] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    query_string: str | None = None,
) -> bytes:
    query = """
query ProcessQuery($first: Int!, $after: Int!, $sortBy: [GraphqlSort!], $filterBy: [GraphqlFilter!], $query: String) {
  processes(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy, query: $query) {
    page {
      processId
      isTask
      lastStep
      lastStatus
      assignee
      failedReason
      traceback
      workflowId
      workflowName
      createdBy
      startedAt
      lastModifiedAt
      form
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
                "query": query_string,
            },
        }
    ).encode("utf-8")


def get_processes_query_with_subscriptions(
    first: int = 10,
    after: int = 0,
    filter_by: list[str] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    query_string: str | None = None,
) -> bytes:
    query = """
query ProcessQuery($first: Int!, $after: Int!, $sortBy: [GraphqlSort!], $filterBy: [GraphqlFilter!], $query: String) {
  processes(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy, query: $query) {
    page {
      processId
      isTask
      lastStep
      lastStatus
      assignee
      failedReason
      traceback
      workflowId
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
                "query": query_string,
            },
        }
    ).encode("utf-8")


def get_processes_state_updates_and_delta(
    first: int = 10,
    after: int = 0,
    filter_by: list[dict[str, str]] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    query_string: str | None = None,
) -> bytes:
    query = """
query ProcessQuery($first: Int!, $after: Int!, $sortBy: [GraphqlSort!], $filterBy: [GraphqlFilter!], $query: String) {
  processes(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy, query: $query) {
    page {
      steps {
        stateDelta
        status
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
                "query": query_string,
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
    assert processes[1]["startedAt"] == "2020-01-15T09:30:00+00:00"
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

    assert processes[0]["startedAt"] == "2020-02-19T09:30:00+00:00"
    assert processes[1]["startedAt"] == "2020-02-19T09:30:00+00:00"
    assert processes[2]["startedAt"] == "2020-02-18T09:30:00+00:00"
    assert processes[3]["startedAt"] == "2020-02-17T09:30:00+00:00"
    assert processes[4]["startedAt"] == "2020-02-16T09:30:00+00:00"


@pytest.mark.parametrize(
    "query_args",
    [
        {"filter_by": [{"field": "lastStatus", "value": "completed"}]},
        {"query_string": "lastStatus:completed"},
        {"query_string": "last_status:completed"},
    ],
)
def test_processes_has_filtering(
    test_client,
    mocked_processes,
    mocked_processes_resumeall,
    generic_subscription_2,
    generic_subscription_1,
    query_args,
):
    # when

    data = get_processes_query(**query_args)
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
            "message": (
                "Invalid filter arguments (invalid_filters=['test'] "
                "valid_filter_keys=['assignee', 'createdBy', "
                "'customer', 'failedReason', 'isTask', 'lastModifiedAt', 'lastStatus', "
                "'lastStep', 'processId', 'product', 'productDescription', 'startedAt', "
                "'subscriptionId', 'tag', 'target', 'traceback', 'workflowId', "
                "'workflowName'])"
            ),
            "path": ["processes"],
            "extensions": {"error_type": "bad_request"},
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


@pytest.mark.parametrize(
    "query_args,num_results",
    [
        ({"query_string": "isTask:no", "first": 20}, 0),
        ({"filter_by": [{"field": "isTask", "value": "false"}], "first": 20}, 6),
        ({"query_string": 'isTask:"true"', "first": 20}, 13),
        ({"query_string": "isTask:(true|false)", "first": 20}, 19),
        ({"query_string": "nonsense"}, 0),
        ({"filter_by": [{"field": "assignee", "value": ""}]}, 0),
        ({"query_string": None, "first": 100}, 19),
        ({"query_string": "one"}, 8),
        ({"query_string": "two"}, 7),
        ({"query_string": "product:(1 | 3)"}, 8),
        ({"query_string": "tag:gen1"}, 8),
        ({"query_string": "tag:gEN2"}, 7),
        ({"query_string": "-tag:gen*"}, 4),
    ],
)
def test_processes_various_filterings(
    test_client,
    mocked_processes,
    mocked_processes_resumeall,
    generic_subscription_2,
    generic_subscription_1,
    query_args,
    num_results,
):
    # when
    with patch.object(app_settings, "FILTER_BY_MODE", "partial"):
        data = get_processes_query(**query_args)
        response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    processes_data = result["data"]["processes"]
    processes = processes_data["page"]
    assert len(processes) == num_results


@pytest.mark.parametrize(
    "query_args",
    [
        lambda pid: {"filter_by": [{"field": "processId", "value": pid}]},
        lambda pid: {"query_string": f"processId:{pid}"},
        lambda pid: {"query_string": f"process_id:{pid}"},
    ],
)
def test_single_process(
    test_client,
    mocked_processes,
    mocked_processes_resumeall,
    generic_subscription_2,
    generic_subscription_1,
    query_args,
):
    process_pid = str(mocked_processes[0])
    # when

    data = get_processes_query(**query_args(process_pid))
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


def test_single_process_with_form(
    test_client,
    mocked_processes,
    generic_subscription_2,
    generic_subscription_1,
):
    process_pid = str(mocked_processes[1])
    # when

    data = get_processes_query(filter_by=[{"field": "process_id", "value": process_pid}])
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
    assert processes[0]["form"] == {
        "title": "unknown",
        "type": "object",
        "properties": {"generic_select": {"$ref": "#/$defs/TestChoice"}},
        "additionalProperties": False,
        "required": ["generic_select"],
        "$defs": {"TestChoice": {"enum": ["A", "B", "C"], "title": "TestChoice", "type": "string"}},
    }


@pytest.mark.parametrize(
    "query_args",
    [
        lambda pid: {"filter_by": [{"field": "processId", "value": pid}]},
        lambda pid: {"query_string": f"processId:{pid}"},
        lambda pid: {"query_string": f"process_id:{pid}"},
    ],
)
def test_single_process_with_subscriptions(
    test_client,
    mocked_processes,
    mocked_processes_resumeall,
    generic_subscription_2,
    generic_subscription_1,
    query_args,
):
    process_pid = str(mocked_processes[0])
    # when

    data = get_processes_query_with_subscriptions(**query_args(process_pid))
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


@pytest.mark.parametrize(
    "query_args",
    [
        lambda pid: {"filter_by": [{"field": "processId", "value": pid}]},
        lambda pid: {"query_string": f"processId:{pid}"},
        lambda pid: {"query_string": f"process_id:{pid}"},
    ],
)
def test_processes_state_updates_and_delta(
    test_client,
    mocked_processes,
    mocked_processes_resumeall,
    generic_subscription_2,
    generic_subscription_1,
    query_args,
):
    # when

    process_pid = str(mocked_processes[0])
    data = get_processes_state_updates_and_delta(**query_args(process_pid))
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    # then

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    assert "errors" not in result
    processes_data = result["data"]["processes"]
    processes = processes_data["page"]

    assert [process["steps"] for process in processes] == [
        [
            {"stateDelta": {}, "status": "success"},
            {
                "stateDelta": {"subscription_id": generic_subscription_1},
                "status": "success",
            },
            {"stateDelta": {}, "status": "success"},
            {"stateDelta": {}, "status": "suspend"},
            {"stateDelta": None, "status": "pending"},
            {"stateDelta": None, "status": "pending"},
        ]
    ]
