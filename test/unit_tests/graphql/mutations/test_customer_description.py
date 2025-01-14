import json

from orchestrator.db import SubscriptionCustomerDescriptionTable, db
from test.unit_tests.config import GRAPHQL_ENDPOINT, GRAPHQL_HEADERS
from test.unit_tests.graphql.mutations.helpers import mutation_authorization


def get_customer_description_upsert_mutation(
    customer_id: str,
    subscription_id: str,
    description: str,
    version=None,
) -> bytes:
    query = """
mutation CustomerDescriptionUpsertMutation ($customerId: String!, $subscriptionId: UUID!, $description: String!, $version: Int) {
    upsertCustomerDescription(customerId: $customerId, subscriptionId: $subscriptionId, description: $description, version: $version) {
        ... on CustomerDescription {
            customerId
            subscriptionId
            description
            version
        }

        ... on NotFoundError {
            message
        }
        ... on MutationError {
            message
        }
    }
}
    """
    return json.dumps(
        {
            "operationName": "CustomerDescriptionUpsertMutation",
            "query": query,
            "variables": {
                "customerId": customer_id,
                "subscriptionId": subscription_id,
                "description": description,
                "version": version,
            },
        }
    ).encode("utf-8")


def get_customer_description_remove_mutation(
    customer_id: str,
    subscription_id: str,
) -> bytes:
    query = """
mutation CustomerDescriptionRemoveMutation ($customerId: String!, $subscriptionId: UUID!) {
    removeCustomerDescription(customerId: $customerId, subscriptionId: $subscriptionId) {
        ... on CustomerDescription {
            customerId
            subscriptionId
            description
            version
        }

        ... on NotFoundError {
            message
        }
    }
}
    """
    return json.dumps(
        {
            "operationName": "CustomerDescriptionRemoveMutation",
            "query": query,
            "variables": {
                "customerId": customer_id,
                "subscriptionId": subscription_id,
            },
        }
    ).encode("utf-8")


def test_customer_description_create(httpx_mock, test_client, product_sub_list_union_subscription_1):
    # given

    subscription_id = str(product_sub_list_union_subscription_1)
    customer_id = "0c43b714-0a11-e511-80d0-005056956c1a"
    description = "create description"

    # when

    query = get_customer_description_upsert_mutation(customer_id, subscription_id, description)

    with mutation_authorization():
        response = test_client.post(GRAPHQL_ENDPOINT, content=query, headers=GRAPHQL_HEADERS)

    # then

    assert response.json() == {
        "data": {
            "upsertCustomerDescription": {
                "customerId": "0c43b714-0a11-e511-80d0-005056956c1a",
                "subscriptionId": subscription_id,
                "description": "create description",
                "version": 1,
            }
        }
    }


def test_customer_description_create_not_found_error(httpx_mock, test_client):
    # given

    subscription_id = "50b44ca0-25f6-40d4-b2af-f0418bf2e81a"
    customer_id = "0c43b714-0a11-e511-80d0-005056956c1a"
    description = "create description"

    # when

    query = get_customer_description_upsert_mutation(customer_id, subscription_id, description)

    with mutation_authorization():
        response = test_client.post(GRAPHQL_ENDPOINT, content=query, headers=GRAPHQL_HEADERS)

    # then

    assert response.json() == {
        "data": {
            "upsertCustomerDescription": {
                "message": "Subscription not found",
            }
        }
    }


def test_customer_description_update(httpx_mock, test_client, product_sub_list_union_subscription_1):
    # given

    subscription_id = str(product_sub_list_union_subscription_1)
    customer_id = "0c43b714-0a11-e511-80d0-005056956c1a"
    description = "update description"

    customer_description = SubscriptionCustomerDescriptionTable(
        customer_id=customer_id,
        subscription_id=subscription_id,
        description="create description",
    )
    db.session.add(customer_description)
    db.session.commit()

    # when
    query = get_customer_description_upsert_mutation(customer_id, subscription_id, description)

    with mutation_authorization():
        response = test_client.post(GRAPHQL_ENDPOINT, content=query, headers=GRAPHQL_HEADERS)

    # then

    assert response.json() == {
        "data": {
            "upsertCustomerDescription": {
                "customerId": "0c43b714-0a11-e511-80d0-005056956c1a",
                "subscriptionId": subscription_id,
                "description": "update description",
                "version": 2,
            }
        }
    }


def test_customer_description_update_with_version(httpx_mock, test_client, product_sub_list_union_subscription_1):
    # given

    subscription_id = str(product_sub_list_union_subscription_1)
    customer_id = "0c43b714-0a11-e511-80d0-005056956c1a"
    description = "update description"
    version = 1

    customer_description = SubscriptionCustomerDescriptionTable(
        customer_id=customer_id,
        subscription_id=subscription_id,
        description="create description",
        version=version,
    )
    db.session.add(customer_description)
    db.session.commit()

    # when
    query = get_customer_description_upsert_mutation(customer_id, subscription_id, description, version)

    with mutation_authorization():
        response = test_client.post(GRAPHQL_ENDPOINT, content=query, headers=GRAPHQL_HEADERS)

    # then

    assert response.json() == {
        "data": {
            "upsertCustomerDescription": {
                "customerId": "0c43b714-0a11-e511-80d0-005056956c1a",
                "subscriptionId": subscription_id,
                "description": "update description",
                "version": version + 1,
            }
        }
    }


def test_customer_description_update_with_incorrect_version(
    httpx_mock, test_client, product_sub_list_union_subscription_1
):
    # given

    subscription_id = str(product_sub_list_union_subscription_1)
    customer_id = "0c43b714-0a11-e511-80d0-005056956c1a"
    description = "update description"
    version = 0

    customer_description = SubscriptionCustomerDescriptionTable(
        customer_id=customer_id,
        subscription_id=subscription_id,
        description="create description",
        version=1,
    )
    db.session.add(customer_description)
    db.session.commit()

    # when
    query = get_customer_description_upsert_mutation(customer_id, subscription_id, description, version)

    with mutation_authorization():
        response = test_client.post(GRAPHQL_ENDPOINT, content=query, headers=GRAPHQL_HEADERS)

    # then

    assert response.json() == {
        "data": {
            "upsertCustomerDescription": {
                "message": "Stale data: given version (0) does not match the current version (1)",
            },
        },
    }


def test_customer_description_delete(httpx_mock, test_client, product_sub_list_union_subscription_1):
    # given

    subscription_id = str(product_sub_list_union_subscription_1)
    customer_id = "0c43b714-0a11-e511-80d0-005056956c1a"

    customer_description = SubscriptionCustomerDescriptionTable(
        customer_id=customer_id,
        subscription_id=subscription_id,
        description="create description",
    )
    db.session.add(customer_description)
    db.session.commit()

    # when

    query = get_customer_description_remove_mutation(customer_id, subscription_id)

    with mutation_authorization():
        response = test_client.post(GRAPHQL_ENDPOINT, content=query, headers=GRAPHQL_HEADERS)

    # then

    assert response.json() == {
        "data": {
            "removeCustomerDescription": {
                "customerId": "0c43b714-0a11-e511-80d0-005056956c1a",
                "subscriptionId": subscription_id,
                "description": "create description",
                "version": 1,
            }
        }
    }


def test_customer_description_delete_not_found_error(httpx_mock, test_client, product_sub_list_union_subscription_1):
    # given

    subscription_id = str(product_sub_list_union_subscription_1)
    customer_id = "0c43b714-0a11-e511-80d0-005056956c1a"

    # when

    query = get_customer_description_remove_mutation(customer_id, subscription_id)

    with mutation_authorization():
        response = test_client.post(GRAPHQL_ENDPOINT, content=query, headers=GRAPHQL_HEADERS)

    # then

    assert response.json() == {
        "data": {
            "removeCustomerDescription": {
                "message": "Customer description not found",
            }
        }
    }
