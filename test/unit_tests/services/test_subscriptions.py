import datetime
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy.orm.exc import MultipleResultsFound

from orchestrator.db import ProductTable
from orchestrator.domain import SubscriptionModel
from orchestrator.services.subscriptions import (
    build_extended_domain_model,
    format_extended_domain_model,
    get_subscription,
    retrieve_subscription_by_subscription_instance_value,
)
from orchestrator.utils.json import json_dumps, json_loads
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


def test_build_extended_domain_model(generic_subscription_1, generic_product_1):
    subscription = SubscriptionModel.from_subscription(generic_subscription_1)
    extended_model = build_extended_domain_model(subscription)
    actual = json_loads(json_dumps(extended_model))

    # Remove dates from the result and just verify their type
    assert isinstance(actual.pop("start_date"), datetime.datetime)
    datetime.datetime.fromisoformat(actual["product"].pop("created_at"))

    assert actual == {
        "customer_descriptions": [],
        "customer_id": "2f47f65a-0911-e511-80d0-005056956c1a",
        "description": "Generic Subscription One",
        "end_date": None,
        "insync": True,
        "note": None,
        "pb_1": {
            "label": None,
            "name": "PB_1",
            "owner_subscription_id": generic_subscription_1,
            "rt_1": "Value1",
            "subscription_instance_id": str(subscription.pb_1.subscription_instance_id),
        },
        "pb_2": {
            "label": None,
            "name": "PB_2",
            "owner_subscription_id": generic_subscription_1,
            "rt_2": 42,
            "rt_3": "Value2",
            "subscription_instance_id": str(subscription.pb_2.subscription_instance_id),
        },
        "product": {
            # "created_at": "2022-12-20T10:36:36+00:00",
            "description": "Generic Product One",
            "end_date": None,
            "name": "Product 1",
            "product_id": str(generic_product_1.product_id),
            "product_type": "Generic",
            "status": "active",
            "tag": "GEN1",
        },
        # "start_date": datetime.datetime(2022, 12, 20, 10, 36, 36, tzinfo=datetime.timezone.utc),
        "status": "active",
        "subscription_id": generic_subscription_1,
    }


def test_format_extended_domain_model(generic_subscription_1, generic_product_1):
    subscription = SubscriptionModel.from_subscription(generic_subscription_1)
    extended_model = build_extended_domain_model(subscription)

    # For the sake of testing, inject 2 in_use_by_ids on the subscription dict; 1 of which belongs
    # to the owner
    other_instance_id = uuid4()
    in_use_by_ids = [subscription.pb_1.subscription_instance_id, other_instance_id]
    extended_model["pb_1"]["in_use_by_ids"] = in_use_by_ids

    # Without filtering we should see the instance_id from the owner subscription
    formatted_no_filter = format_extended_domain_model(deepcopy(extended_model), filter_owner_relations=False)
    assert sorted(formatted_no_filter["pb_1"]["in_use_by_ids"]) == sorted(in_use_by_ids)

    # With filtering we should not see the instance_id from the owner subscription
    formatted_with_filter = format_extended_domain_model(deepcopy(extended_model), filter_owner_relations=True)
    assert sorted(formatted_with_filter["pb_1"]["in_use_by_ids"]) == [other_instance_id]
