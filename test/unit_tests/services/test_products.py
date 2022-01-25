from uuid import uuid4

import pytest
from sqlalchemy.orm.exc import NoResultFound

from orchestrator.db import ProductTable
from orchestrator.services.products import get_product_by_id, get_product_by_name, get_tags, get_types


def test_get_product_by_id(generic_product_1):
    product = ProductTable.query.filter(ProductTable.name == "Product 1").one()

    result = get_product_by_id(product.product_id)
    assert result.product_id == product.product_id


def test_get_product_by_id_err(generic_product_1):
    assert get_product_by_id(uuid4()) is None


def test_get_product_by_name(generic_product_1):
    product = ProductTable.query.filter(ProductTable.name == "Product 1").one()

    result = get_product_by_name(product.name)
    assert result.product_id == product.product_id


def test_get_product_by_name_err(generic_product_1):
    with pytest.raises(NoResultFound):
        assert get_product_by_name("") is None


def test_get_types(generic_product_1):
    assert get_types() == ["Generic"]


def test_get_tags(generic_product_1):
    assert get_tags() == ["GEN1"]
