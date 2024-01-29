from copy import deepcopy
from unittest import mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from orchestrator.forms.validators import ProductId, product_id
from pydantic_forms.core import FormPage
from test.unit_tests.helpers import URL_MISSING, URL_PARSING, URL_VALUE


@mock.patch("orchestrator.forms.validators.product_id.get_product_by_id")
def test_product_id(mock_get_product_by_id):
    product_x_id = uuid4()
    product_y_id = uuid4()

    mock_get_product_by_id.side_effect = [product_x_id, product_y_id]

    class Form(FormPage):
        product_x: product_id([product_x_id])
        product_id: ProductId

    data = Form(product_id=product_y_id, product_x=product_x_id)
    assert data.product_x == product_x_id
    assert data.product_id == product_y_id
    mock_get_product_by_id.assert_has_calls(
        [mock.call(product_x_id, join_fixed_inputs=False), mock.call(product_y_id, join_fixed_inputs=False)]
    )


def test_product_id_schema():
    product_x_id = uuid4()

    class Form(FormPage):
        product_x: product_id([product_x_id])
        product_id: ProductId

    assert Form.model_json_schema() == {
        "additionalProperties": False,
        "properties": {
            "product_id": {"format": "productId", "title": "Product Id", "type": "string"},
            "product_x": {
                "format": "productId",
                "title": "Product X",
                "type": "string",
                "uniforms": {"productIds": [str(product_x_id)]},
            },
        },
        "required": ["product_x", "product_id"],
        "title": "unknown",
        "type": "object",
    }


def stringify_exceptions(error_list):
    # without this the error lists are not considered equal
    list_copy = deepcopy(error_list)
    for error in list_copy:
        if "error" in error.get("ctx", {}):
            error["ctx"]["error"] = str(error["ctx"]["error"])
    return list_copy


@mock.patch("orchestrator.forms.validators.product_id.get_product_by_id")
def test_product_id_nok(mock_get_product_by_id):
    product_x_id = uuid4()
    product_y_id = uuid4()

    mock_get_product_by_id.side_effect = [product_y_id, None]

    class Form(FormPage):
        product_x: product_id([product_x_id])
        product_id: ProductId

    with pytest.raises(ValidationError) as error_info:
        Form(product_id=product_y_id, product_x=product_y_id)

    expected = [
        {
            "ctx": {"error": f"value is not a valid enumeration member; permitted: '{product_x_id}'"},
            "input": product_y_id,
            "loc": ("product_x",),
            "msg": f"Value error, value is not a valid enumeration member; permitted: '{product_x_id}'",
            "type": "value_error",
        }
        | URL_VALUE,
        {
            "type": "value_error",
            "loc": ("product_id",),
            "msg": "Value error, Product not found",
            "input": product_y_id,
            "ctx": {"error": ValueError("Product not found")},
        }
        | URL_VALUE,
    ]

    actual = error_info.value.errors()
    assert stringify_exceptions(expected) == stringify_exceptions(actual)
    mock_get_product_by_id.assert_has_calls(
        [mock.call(product_y_id, join_fixed_inputs=False), mock.call(product_y_id, join_fixed_inputs=False)]
    )

    with pytest.raises(ValidationError) as error_info:
        Form(product_id="INCOMPLETE")

    expected = [
        {"type": "missing", "loc": ("product_x",), "msg": "Field required", "input": {"product_id": "INCOMPLETE"}}
        | URL_MISSING,
        {
            "type": "uuid_parsing",
            "loc": ("product_id",),
            "msg": "Input should be a valid UUID, invalid character: expected an optional prefix of `urn:uuid:` followed by [0-9a-fA-F-], found `I` at 1",
            "input": "INCOMPLETE",
            "ctx": {
                "error": "invalid character: expected an optional prefix of `urn:uuid:` followed by [0-9a-fA-F-], found `I` at 1"
            },
        }
        | URL_PARSING,
    ]
    assert expected == error_info.value.errors()
