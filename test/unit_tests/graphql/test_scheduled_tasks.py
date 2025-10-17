import json
from http import HTTPStatus

from orchestrator.schedules.scheduler import get_scheduler


def get_scheduled_tasks_query(
    first: int = 10,
    after: int = 0,
    filter_by: list[dict[str, str]] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    query_string: str | None = None,
) -> bytes:
    query = """
query ScheduledTasksQuery($first: Int!, $after: Int!, $filterBy: [GraphqlFilter!], $sortBy: [GraphqlSort!]) {
  scheduledTasks(first: $first, after: $after, filterBy: $filterBy, sortBy: $sortBy) {
    page {
      id
      name
      nextRunTime
      trigger
    }
    pageInfo {
      endCursor
      hasNextPage
      hasPreviousPage
      startCursor
      totalItems
    }
  }
}
    """
    return json.dumps(
        {
            "operationName": "ScheduledTasksQuery",
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


def test_scheduled_tasks_query(test_client):
    with get_scheduler():
        pass

    data = get_scheduled_tasks_query(first=2)
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code, response.text
    result = response.json()
    scheduled_tasks_data = result["data"]["scheduledTasks"]
    scheduled_tasks = scheduled_tasks_data["page"]
    pageinfo = scheduled_tasks_data["pageInfo"]

    assert "errors" not in result
    assert len(scheduled_tasks) == 2

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 1,
        "totalItems": 4,
    }


def test_scheduled_tasks_has_previous_page(test_client):
    data = get_scheduled_tasks_query(after=1, sort_by=[{"field": "name", "order": "ASC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code, response.text
    result = response.json()
    scheduled_tasks_data = result["data"]["scheduledTasks"]
    scheduled_tasks = scheduled_tasks_data["page"]
    pageinfo = scheduled_tasks_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "hasNextPage": False,
        "hasPreviousPage": True,
        "startCursor": 1,
        "endCursor": 3,
        "totalItems": 4,
    }

    assert len(scheduled_tasks) == 3


def test_scheduled_tasks_filter(test_client):
    data = get_scheduled_tasks_query(
        filter_by=[{"field": "name", "value": "validat"}], sort_by=[{"field": "name", "order": "ASC"}]
    )
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code, response.text
    result = response.json()
    scheduled_tasks_data = result["data"]["scheduledTasks"]
    scheduled_tasks = scheduled_tasks_data["page"]
    pageinfo = scheduled_tasks_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "endCursor": 1,
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "totalItems": 2,
    }
    expected_workflows = [
        "subscriptions-validator",
        "validate-products",
    ]
    assert [job["id"] for job in scheduled_tasks] == expected_workflows


def test_scheduled_tasks_invalid_filter(test_client):
    data = get_scheduled_tasks_query(filter_by=[{"field": "idd", "value": "validate"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code, response.text
    result = response.json()
    scheduled_tasks_data = result["data"]["scheduledTasks"]
    scheduled_tasks = scheduled_tasks_data["page"]
    pageinfo = scheduled_tasks_data["pageInfo"]

    expected_error_msg = (
        "Invalid filter arguments (invalid_filters=['idd'] valid_filter_keys"
        "=['id', 'name', 'nextRunTime', 'next_run_time', 'trigger'])"
    )

    assert pageinfo == {
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": None,
        "endCursor": -1,
        "totalItems": 0,
    }
    assert len(result["errors"]) == 1
    assert result["errors"][0]["message"] == expected_error_msg
    assert not scheduled_tasks


def test_scheduled_tasks_sort_by(test_client):
    data = get_scheduled_tasks_query(sort_by=[{"field": "name", "order": "DESC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code, response.text
    result = response.json()
    scheduled_tasks_data = result["data"]["scheduledTasks"]
    scheduled_tasks = scheduled_tasks_data["page"]
    pageinfo = scheduled_tasks_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "endCursor": 3,
        "totalItems": 4,
    }
    expected_workflows = [
        "Validate Products and inactive subscriptions",
        "Subscriptions Validator",
        "Resume workflows",
        "Clean up tasks",
    ]
    assert [job["name"] for job in scheduled_tasks] == expected_workflows


def test_scheduled_tasks_invalid_sort(test_client):
    data = get_scheduled_tasks_query(sort_by=[{"field": "namee", "order": "DESC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code, response.text
    result = response.json()
    scheduled_tasks_data = result["data"]["scheduledTasks"]
    scheduled_tasks = scheduled_tasks_data["page"]
    pageinfo = scheduled_tasks_data["pageInfo"]

    expected_error_msg = (
        "Invalid sort arguments (invalid_sorting=['namee'] valid_sort_keys"
        "=['id', 'name', 'nextRunTime', 'next_run_time', 'trigger'])"
    )

    assert pageinfo == {
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "endCursor": 3,
        "totalItems": 4,
    }
    assert len(result["errors"]) == 1
    assert result["errors"][0]["message"] == expected_error_msg
    assert len(scheduled_tasks) == 4
