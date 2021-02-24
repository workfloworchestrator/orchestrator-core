from uuid import uuid4

import pytest
from sqlalchemy.orm.exc import MultipleResultsFound

from orchestrator.db import ProductTable
from orchestrator.services.subscriptions import get_subscription, retrieve_subscription_by_subscription_instance_value
from test.unit_tests import fixtures

CORRECT_SUBSCRIPTION = str(uuid4())
INCORRECT_SUBSCRIPTION = str(uuid4())

subscription_mapping = {"PB_2": [{"rt_3": "info.id", "rt_2": "info2.id"}]}


def test_get_subscription_by_id(generic_product_3):
    values = {"info.id": "0", "info2.id": "X"}
    product = ProductTable.query.filter(ProductTable.name == "Product 3").one()
    subscription = fixtures.create_subscription_for_mapping(
        product, subscription_mapping, values, subscription_id=CORRECT_SUBSCRIPTION
    )
    result = get_subscription(str(subscription.subscription_id))
    assert str(result.subscription_id) == CORRECT_SUBSCRIPTION


def test_get_subscription_by_id_err(generic_product_3):
    values = {"info.id": "0", "info2.id": "X"}
    product = ProductTable.query.filter(ProductTable.name == "Product 3").one()
    fixtures.create_subscription_for_mapping(
        product, subscription_mapping, values, subscription_id=CORRECT_SUBSCRIPTION
    )

    with pytest.raises(ValueError):
        get_subscription(INCORRECT_SUBSCRIPTION)


def test_retrieve_subscription_by_subscription_instance_value_none(generic_product_3):
    values = {"info.id": "0", "info2.id": "X"}
    product = ProductTable.query.filter(ProductTable.name == "Product 3").one()
    fixtures.create_subscription_for_mapping(product, subscription_mapping, values)

    assert retrieve_subscription_by_subscription_instance_value("rt_2", "Wrong") is None


def test_retrieve_subscription_by_subscription_instance_value(generic_product_3):
    values = {"info.id": "0", "info2.id": "X"}
    product = ProductTable.query.filter(ProductTable.name == "Product 3").one()
    fixtures.create_subscription_for_mapping(
        product, subscription_mapping, values, subscription_id=CORRECT_SUBSCRIPTION
    )

    assert (
        str(retrieve_subscription_by_subscription_instance_value("rt_3", "0").subscription_id) == CORRECT_SUBSCRIPTION
    )


def test_retrieve_subscription_by_subscription_instance_value_err(generic_product_3):
    values = {"info.id": "0", "info2.id": "X"}
    product = ProductTable.query.filter(ProductTable.name == "Product 3").one()
    fixtures.create_subscription_for_mapping(product, subscription_mapping, values)
    fixtures.create_subscription_for_mapping(product, subscription_mapping, values)

    with pytest.raises(MultipleResultsFound):
        retrieve_subscription_by_subscription_instance_value("rt_3", "0")
