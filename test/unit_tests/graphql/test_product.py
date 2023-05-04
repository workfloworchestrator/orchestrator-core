import json
from http import HTTPStatus
from typing import Union

from httpx import Response


def get_product_query(
    first: int = 10,
    after: int = 0,
    filter_by: Union[list[str], None] = None,
    sort_by: Union[list[dict[str, str]], None] = None,
) -> str:
    query = """
query ProductQuery($first: Int!, $after: Int!, $sortBy: [GraphqlSort!], $filterBy: [GraphqlFilter!]) {
  products(first: $first, after: $after, sortBy: $sortBy, filterBy: $filterBy) {
      name
      productType
      tag
      status
      productId
      description
      createdAt
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
    )


def test_product_query(test_client, test_product_list_nested):
    data = get_product_query()
    response: Response = test_client.post("/api/graphql", data=data, headers={"Content-Type": "application/json"})

    assert HTTPStatus.OK == response.status_code
    result = response.json()
    products_data = result["data"]["products"]
    assert len(products_data) == 1
    assert products_data[0]["name"] == "TestProductListNested"
