from uuid import uuid4

import pytest

from orchestrator.db import ProductTable
from orchestrator.services.products import get_product


def test_get_product_by_id(generic_product_1):
    product = ProductTable.query.filter(ProductTable.name == "Product 1").one()

    result = get_product(product.product_id)
    assert result.product_id == product.product_id


def test_get_product_by_id_err(generic_product_1):
    ProductTable.query.filter(ProductTable.name == "Product 1").one()

    with pytest.raises(ValueError):
        get_product(uuid4())
