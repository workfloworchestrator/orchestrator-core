import json
from http import HTTPStatus
from typing import Union

from fastapi import Response


def get_product_query(
    first: int = 10,
    after: int = 0,
    filter_by: Union[list[str], None] = None,
    sort_by: Union[list[dict[str, str]], None] = None,
) -> bytes:
    query = """
query ProductQuery($first: Int!, $after: Int!, $filterBy: [GraphqlFilter!], $sortBy: [GraphqlSort!]) {
  products(first: $first, after: $after, filterBy: $filterBy, sortBy: $sortBy) {
    page {
      createdAt
      description
      endDate
      fixedInputs {
        createdAt
        fixedInputId
        name
        productId
        value
      }
      name
      productBlocks {
        createdAt
        description
        endDate
        name
        productBlockId
        resourceTypes {
          description
          resourceType
          resourceTypeId
        }
        status
        tag
      }
      productId
      productType
      status
      tag
      workflows {
        createdAt
        description
        target
        name
        workflowId
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
            "operationName": "ProductQuery",
            "query": query,
            "variables": {
                "first": first,
                "after": after,
                "sortBy": sort_by if sort_by else [],
                "filterBy": filter_by if filter_by else [],
            },
        }
    ).encode("utf-8")


def test_product_query(test_client, generic_product_1, generic_product_2, generic_product_3):
    data = get_product_query(first=2)
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    products_data = result["data"]["products"]
    products = products_data["page"]
    pageinfo = products_data["pageInfo"]

    assert len(products) == 2

    assert pageinfo == {
        "hasPreviousPage": False,
        "hasNextPage": True,
        "startCursor": 0,
        "endCursor": 1,
        "totalItems": "3",
    }


def test_product_has_previous_page(test_client, generic_product_1, generic_product_2, generic_product_3):
    data = get_product_query(after=1)
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    products_data = result["data"]["products"]
    products = products_data["page"]
    pageinfo = products_data["pageInfo"]

    assert pageinfo == {
        "endCursor": 2,
        "hasNextPage": False,
        "hasPreviousPage": True,
        "startCursor": 1,
        "totalItems": "3",
    }

    assert len(products) == 2
    assert products[0]["name"] == "Product 2"
    assert products[1]["name"] == "Product 3"


def test_products_filter_by_product_block(test_client, generic_product_1, generic_product_2, generic_product_3):
    data = get_product_query(
        filter_by=[{"field": "product_blocks", "value": "PB_1-PB_3"}],
        sort_by=[{"field": "name", "order": "ASC"}],
    )
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert HTTPStatus.OK == response.status_code
    result = response.json()
    products_data = result["data"]["products"]
    products = products_data["page"]
    pageinfo = products_data["pageInfo"]

    assert pageinfo == {
        "endCursor": 1,
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "totalItems": "2",
    }
    assert products[0]["name"] == "Product 1"
    assert products[1]["name"] == "Product 2"


def test_products_sort_by_tag(test_client, generic_product_1, generic_product_2, generic_product_3):
    data = get_product_query(sort_by=[{"field": "tag", "order": "DESC"}])
    response: Response = test_client.post("/api/graphql", content=data, headers={"Content-Type": "application/json"})
    assert HTTPStatus.OK == response.status_code
    result = response.json()

    products_data = result["data"]["products"]
    products = products_data["page"]
    pageinfo = products_data["pageInfo"]

    assert [prod["tag"] for prod in products] == ["GEN3", "GEN2", "GEN1"]
    assert pageinfo == {
        "endCursor": 2,
        "hasNextPage": False,
        "hasPreviousPage": False,
        "startCursor": 0,
        "totalItems": "3",
    }
