import json
from http import HTTPStatus


def get_scheduled_jobs_query(
    first: int = 10,
    after: int = 0,
    filter_by: list[dict[str, str]] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    query_string: str | None = None,
) -> bytes:
    query = """
query ScheduledJobsQuery($first: Int!, $after: Int!, $filterBy: [GraphqlFilter!], $sortBy: [GraphqlSort!]) {
  scheduledJobs(first: $first, after: $after, filterBy: $filterBy, sortBy: $sortBy) {
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
            "operationName": "ScheduledJobsQuery",
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


def test_scheduled_jobs_query(test_client):
    data = get_scheduled_jobs_query(first=2)
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code, response.text
    result = response.json()
    scheduled_jobs_data = result["data"]["scheduledJobs"]
    scheduled_jobs = scheduled_jobs_data["page"]
    pageinfo = scheduled_jobs_data["pageInfo"]

    assert "errors" not in result
    assert len(scheduled_jobs) == 2

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 1,
        "totalItems": 4,
    }


def test_scheduled_jobs_has_previous_page(test_client):
    data = get_scheduled_jobs_query(after=1, sort_by=[{"field": "name", "order": "ASC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code, response.text
    result = response.json()
    scheduled_jobs_data = result["data"]["scheduledJobs"]
    scheduled_jobs = scheduled_jobs_data["page"]
    pageinfo = scheduled_jobs_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "hasNextPage": False,
        "hasPreviousPage": True,
        "startCursor": 1,
        "endCursor": 3,
        "totalItems": 4,
    }

    assert len(scheduled_jobs) == 3


def test_scheduled_jobs_filter(test_client):
    data = get_scheduled_jobs_query(
        filter_by=[{"field": "id", "value": "validate"}], sort_by=[{"field": "name", "order": "ASC"}]
    )
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code, response.text
    result = response.json()
    scheduled_jobs_data = result["data"]["scheduledJobs"]
    scheduled_jobs = scheduled_jobs_data["page"]
    pageinfo = scheduled_jobs_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "endCursor": 1,
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "totalItems": 2,
    }
    expected_workflows = [
        "validate_subscriptions",
        "validate_products",
    ]
    assert [job["id"] for job in scheduled_jobs] == expected_workflows


def test_scheduled_jobs_sort_by(test_client):
    data = get_scheduled_jobs_query(sort_by=[{"field": "name", "order": "DESC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code, response.text
    result = response.json()
    scheduled_jobs_data = result["data"]["scheduledJobs"]
    scheduled_jobs = scheduled_jobs_data["page"]
    pageinfo = scheduled_jobs_data["pageInfo"]

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
    assert [job["name"] for job in scheduled_jobs] == expected_workflows
