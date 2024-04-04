import json
from http import HTTPStatus

import pytest

from test.unit_tests.fixtures.workflows import add_soft_deleted_workflows  # noqa: F401


@pytest.fixture(autouse=True)
def _add_soft_deleted_workflows(add_soft_deleted_workflows):  # noqa: F811
    add_soft_deleted_workflows(10)


@pytest.fixture
def seed_workflows():
    pass


def get_workflows_query(
    first: int = 10,
    after: int = 0,
    filter_by: list[dict[str, str]] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    query_string: str | None = None,
) -> bytes:
    query = """
query WorkflowsQuery($first: Int!, $after: Int!, $filterBy: [GraphqlFilter!], $sortBy: [GraphqlSort!], $query: String) {
  workflows(first: $first, after: $after, filterBy: $filterBy, sortBy: $sortBy, query: $query) {
    page {
      workflowId
      name
      description
      createdAt
      steps {
        name
        assignee
      }
      products {
        name
        description
        tag
      }
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
            "operationName": "WorkflowsQuery",
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


def test_workflows_query(test_client):
    data = get_workflows_query(first=2)
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    workflows_data = result["data"]["workflows"]
    workflows = workflows_data["page"]
    pageinfo = workflows_data["pageInfo"]

    assert "errors" not in result
    assert len(workflows) == 2

    assert all(len(workflow["steps"]) > 0 for workflow in workflows)

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 1,
        "totalItems": 4,
    }


def test_workflows_has_previous_page(test_client):
    data = get_workflows_query(after=1, sort_by=[{"field": "name", "order": "ASC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    workflows_data = result["data"]["workflows"]
    workflows = workflows_data["page"]
    pageinfo = workflows_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "hasNextPage": False,
        "hasPreviousPage": True,
        "startCursor": 1,
        "endCursor": 3,
        "totalItems": 4,
    }

    assert len(workflows) == 3
    assert [workflow["name"] for workflow in workflows] == [
        "task_clean_up_tasks",
        "task_resume_workflows",
        "task_validate_products",
    ]


@pytest.mark.parametrize(
    "query_args",
    [
        {"filter_by": [{"field": "name", "value": "task_"}]},
        {"query_string": "name:task_*"},
    ],
)
def test_workflows_filter_by_name(test_client, query_args):
    data = get_workflows_query(**query_args, sort_by=[{"field": "name", "order": "ASC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    workflows_data = result["data"]["workflows"]
    workflows = workflows_data["page"]
    pageinfo = workflows_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "endCursor": 2,
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "totalItems": 3,
    }
    expected_workflows = ["task_clean_up_tasks", "task_resume_workflows", "task_validate_products"]
    assert [rt["name"] for rt in workflows] == expected_workflows


@pytest.mark.parametrize(
    "query_args",
    [
        {"filter_by": [{"field": "product", "value": "Product 1"}]},
        {"query_string": 'product:"Product 1"'},
    ],
)
def test_workflows_filter_by_product(test_client, query_args):
    data = get_workflows_query(**query_args, sort_by=[{"field": "name", "order": "ASC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    workflows_data = result["data"]["workflows"]
    workflows = workflows_data["page"]
    pageinfo = workflows_data["pageInfo"]
    assert "errors" not in result
    assert pageinfo == {
        "endCursor": 0,
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "totalItems": 1,
    }
    assert workflows[0]["name"] == "modify_note"


@pytest.mark.parametrize(
    "query_args",
    [{"query_string": "tag:gen1"}, {"query_string": "tag:gen2"}, {"query_string": "product:Product"}],
)
def test_workflows_filter_by_tag(test_client, query_args):
    data = get_workflows_query(**query_args, sort_by=[{"field": "name", "order": "ASC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    workflows_data = result["data"]["workflows"]
    workflows = workflows_data["page"]
    pageinfo = workflows_data["pageInfo"]
    assert "errors" not in result
    assert pageinfo == {
        "endCursor": 0,
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "totalItems": 1,
    }
    assert len(workflows) == 1
    assert workflows[0]["name"] == "modify_note"


def test_workflows_sort_by_resource_type_desc(test_client):
    data = get_workflows_query(sort_by=[{"field": "name", "order": "DESC"}])
    response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert HTTPStatus.OK == response.status_code
    result = response.json()

    workflows_data = result["data"]["workflows"]
    workflows = workflows_data["page"]
    pageinfo = workflows_data["pageInfo"]

    assert pageinfo == {
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "endCursor": 3,
        "totalItems": 4,
    }
    expected_workflows = ["task_validate_products", "task_resume_workflows", "task_clean_up_tasks", "modify_note"]
    assert [rt["name"] for rt in workflows] == expected_workflows
