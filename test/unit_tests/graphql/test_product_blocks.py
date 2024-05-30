import json
from http import HTTPStatus

import pytest
from fastapi import Response

from test.unit_tests.helpers import assert_no_diff


def get_product_blocks_query(
    first: int = 10,
    after: int = 0,
    filter_by: list[str] | None = None,
    sort_by: list[dict[str, str]] | None = None,
    query_string: str | None = None,
) -> bytes:
    query = """
query ProductBlocksQuery($first: Int!, $after: Int!, $filterBy: [GraphqlFilter!], $sortBy: [GraphqlSort!], $query: String) {
  productBlocks(first: $first, after: $after, filterBy: $filterBy, sortBy: $sortBy, query: $query) {
    page {
      name
      endDate
      description
      createdAt
      status
      tag
      resourceTypes {
        resourceType
        description
      }
      dependsOn {
        name
        description
      }
      inUseBy {
        name
        description
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
            "operationName": "ProductBlocksQuery",
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


@pytest.mark.parametrize(
    "query_args,num_results",
    [
        ({"query_string": None}, 6),
        ({"query_string": "pb1"}, 1),
        ({"query_string": "test"}, 3),
        ({"query_string": "tag:PB_*"}, 3),
        ({"query_string": "tag:pb3"}, 1),
    ],
)
def test_product_blocks_query(test_client, query_args, num_results):
    data = get_product_blocks_query(**query_args)
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    product_blocks_data = result["data"]["productBlocks"]
    product_blocks = product_blocks_data["page"]
    pageinfo = product_blocks_data["pageInfo"]

    assert len(product_blocks) == num_results

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": num_results - 1,
        "totalItems": num_results,
    }


def test_product_blocks_payload(test_client):
    data = get_product_blocks_query(first=2, sort_by=[{"field": "name", "order": "ASC"}])
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    product_blocks_data = result["data"]["productBlocks"]
    product_blocks = product_blocks_data["page"]
    pageinfo = product_blocks_data["pageInfo"]

    assert len(product_blocks) == 2

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 1,
        "totalItems": 6,
    }

    expected = [
        {
            "name": "PB_1",
            "endDate": None,
            "description": "Generic Product Block 1",
            "createdAt": "2023-05-24T00:00:00+00:00",
            "status": "ACTIVE",
            "tag": "PB1",
            "resourceTypes": [{"resourceType": "rt_1", "description": "Resource Type one"}],
            "dependsOn": [],
            "inUseBy": [],
        },
        {
            "name": "PB_2",
            "endDate": None,
            "description": "Generic Product Block 2",
            "createdAt": "2023-05-24T00:00:00+00:00",
            "status": "ACTIVE",
            "tag": "PB2",
            "resourceTypes": [
                {"resourceType": "rt_2", "description": "Resource Type two"},
                {"resourceType": "rt_3", "description": "Resource Type three"},
            ],
            "dependsOn": [],
            "inUseBy": [],
        },
    ]
    product_blocks.sort(
        key=lambda x: x["name"]
    )  # No sort in the query; sort before the `assert` to prevent flaky tests
    assert product_blocks == expected


@pytest.mark.parametrize(
    "query_args",
    [
        {"filter_by": [{"field": "name", "value": "ForTest"}]},
        {"query_string": "name:(SubBlock* | ProductBlock*)"},
    ],
)
def test_product_block_query_with_relations(test_client, query_args):
    data = get_product_blocks_query(**query_args)
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    product_blocks_data = result["data"]["productBlocks"]
    product_blocks = product_blocks_data["page"]
    pageinfo = product_blocks_data["pageInfo"]

    assert len(product_blocks) == 3
    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": False,
        "startCursor": 0,
        "endCursor": 2,
        "totalItems": 3,
    }

    expected = [
        {
            "name": "SubBlockOneForTest",
            "endDate": None,
            "description": "Test Sub Block One",
            "status": "ACTIVE",
            "tag": "TEST",
            "resourceTypes": [
                {"resourceType": "int_field", "description": ""},
                {"resourceType": "str_field", "description": ""},
            ],
            "dependsOn": [],
            "inUseBy": [{"name": "ProductBlockWithListUnionForTest", "description": "Test Union Sub Block"}],
        },
        {
            "name": "SubBlockTwoForTest",
            "endDate": None,
            "description": "Test Sub Block Two",
            "status": "ACTIVE",
            "tag": "TEST",
            "resourceTypes": [{"resourceType": "int_field_2", "description": ""}],
            "dependsOn": [],
            "inUseBy": [{"name": "ProductBlockWithListUnionForTest", "description": "Test Union Sub Block"}],
        },
        {
            "name": "ProductBlockWithListUnionForTest",
            "endDate": None,
            "description": "Test Union Sub Block",
            "status": "ACTIVE",
            "tag": "TEST",
            "resourceTypes": [
                {"resourceType": "int_field", "description": ""},
                {"resourceType": "str_field", "description": ""},
                {"resourceType": "list_field", "description": ""},
            ],
            "dependsOn": [
                {"name": "SubBlockOneForTest", "description": "Test Sub Block One"},
                {"name": "SubBlockTwoForTest", "description": "Test Sub Block Two"},
            ],
            "inUseBy": [],
        },
    ]

    exclude_paths = [f"root[{i}]['createdAt']" for i in range(len(expected))]
    assert_no_diff(expected, product_blocks, exclude_paths=exclude_paths)


def test_product_blocks_has_previous_page(test_client):
    data = get_product_blocks_query(after=1)
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    product_blocks_data = result["data"]["productBlocks"]
    product_blocks = product_blocks_data["page"]
    pageinfo = product_blocks_data["pageInfo"]

    assert pageinfo == {
        "hasNextPage": False,
        "hasPreviousPage": True,
        "startCursor": 1,
        "endCursor": 5,
        "totalItems": 6,
    }

    assert len(product_blocks) == 5
    product_blocks.sort(key=lambda x: x["name"])  # No sort in the query; sort before the assert to prevent flaky tests
    assert product_blocks[0]["name"] == "PB_2"
    assert product_blocks[1]["name"] == "PB_3"


@pytest.mark.parametrize(
    "query_args",
    [
        {"filter_by": [{"field": "resourceType", "value": "rt_1"}]},
        {"query_string": "resourceType:rt_1"},
    ],
)
def test_product_blocks_filter_by_resource_types(test_client, query_args):
    data = get_product_blocks_query(**query_args, sort_by=[{"field": "name", "order": "ASC"}])
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    product_blocks_data = result["data"]["productBlocks"]
    product_blocks = product_blocks_data["page"]
    pageinfo = product_blocks_data["pageInfo"]

    assert pageinfo == {
        "endCursor": 0,
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "totalItems": 1,
    }
    assert product_blocks[0]["name"] == "PB_1"


def test_product_blocks_filter_by_products(test_client):
    data = get_product_blocks_query(
        filter_by=[{"field": "product", "value": "Product 1|Product 3"}],
        sort_by=[{"field": "name", "order": "ASC"}],
    )
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    product_blocks_data = result["data"]["productBlocks"]
    product_blocks = product_blocks_data["page"]
    pageinfo = product_blocks_data["pageInfo"]

    assert pageinfo == {
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "endCursor": 1,
        "totalItems": 2,
    }
    assert product_blocks[0]["name"] == "PB_1"
    assert product_blocks[1]["name"] == "PB_2"


def test_product_blocks_sort_by_tag(test_client):
    data = get_product_blocks_query(sort_by=[{"field": "tag", "order": "DESC"}])
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert HTTPStatus.OK == response.status_code
    result = response.json()

    product_blocks_data = result["data"]["productBlocks"]
    product_blocks = product_blocks_data["page"]
    pageinfo = product_blocks_data["pageInfo"]

    assert [p_block["tag"] for p_block in product_blocks] == ["TEST", "TEST", "TEST", "PB3", "PB2", "PB1"]
    assert pageinfo == {
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "endCursor": 5,
        "totalItems": 6,
    }
