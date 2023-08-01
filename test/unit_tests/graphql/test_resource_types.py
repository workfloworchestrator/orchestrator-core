import json
from http import HTTPStatus
from typing import Union

from fastapi import Response


def get_resource_types_query(
    first: int = 10,
    after: int = 0,
    filter_by: Union[list[str], None] = None,
    sort_by: Union[list[dict[str, str]], None] = None,
) -> bytes:
    query = """
query ResourceTypesQuery($first: Int!, $after: Int!, $filterBy: [GraphqlFilter!], $sortBy: [GraphqlSort!]) {
  resourceTypes(first: $first, after: $after, filterBy: $filterBy, sortBy: $sortBy) {
    page {
      resourceTypeId
      resourceType
      description
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
            "operationName": "ResourceTypesQuery",
            "query": query,
            "variables": {
                "first": first,
                "after": after,
                "sortBy": sort_by if sort_by else [],
                "filterBy": filter_by if filter_by else [],
            },
        }
    ).encode("utf-8")


def test_resource_types_query(test_client):
    data = get_resource_types_query(first=2)
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    resource_types_data = result["data"]["resourceTypes"]
    resource_types = resource_types_data["page"]
    pageinfo = resource_types_data["pageInfo"]

    assert "errors" not in result
    assert len(resource_types) == 2

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 1,
        "totalItems": 7,
    }


def test_resource_types_has_previous_page(test_client):
    data = get_resource_types_query(after=1)
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    resource_types_data = result["data"]["resourceTypes"]
    resource_types = resource_types_data["page"]
    pageinfo = resource_types_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "endCursor": 6,
        "hasNextPage": False,
        "hasPreviousPage": True,
        "startCursor": 1,
        "totalItems": 7,
    }

    assert len(resource_types) == 6
    assert resource_types[0]["resourceType"] == "rt_2"
    assert resource_types[1]["resourceType"] == "rt_3"


def test_resource_types_filter_by_resource_type(test_client):
    data = get_resource_types_query(
        filter_by=[{"field": "resourceType", "value": "rt_"}],
        sort_by=[{"field": "resourceType", "order": "ASC"}],
    )
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    resource_types_data = result["data"]["resourceTypes"]
    resource_types = resource_types_data["page"]
    pageinfo = resource_types_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "endCursor": 2,
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "totalItems": 3,
    }
    assert [rt["resourceType"] for rt in resource_types] == ["rt_1", "rt_2", "rt_3"]


def test_resource_types_filter_by_product_blocks(test_client):
    data = get_resource_types_query(
        filter_by=[{"field": "productBlocks", "value": "PB_1"}],
        sort_by=[{"field": "resourceType", "order": "ASC"}],
    )
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    resource_types_data = result["data"]["resourceTypes"]
    resource_types = resource_types_data["page"]
    pageinfo = resource_types_data["pageInfo"]

    assert "errors" not in result
    assert pageinfo == {
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "endCursor": 0,
        "totalItems": 1,
    }
    assert resource_types[0]["resourceType"] == "rt_1"


def test_resource_types_sort_by_resource_type_desc(test_client):
    data = get_resource_types_query(sort_by=[{"field": "resourceType", "order": "DESC"}])
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert HTTPStatus.OK == response.status_code
    result = response.json()

    resource_types_data = result["data"]["resourceTypes"]
    resource_types = resource_types_data["page"]
    pageinfo = resource_types_data["pageInfo"]

    assert pageinfo == {
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "endCursor": 6,
        "totalItems": 7,
    }
    expected_rts = ["str_field", "rt_3", "rt_2", "rt_1", "list_field", "int_field_2", "int_field"]
    assert [rt["resourceType"] for rt in resource_types] == expected_rts
