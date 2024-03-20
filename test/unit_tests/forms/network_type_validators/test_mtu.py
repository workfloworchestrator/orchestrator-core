import pytest
from pydantic import TypeAdapter, ValidationError

from orchestrator.forms.validators import MTU
from test.unit_tests.forms.test_generic_validators import stringify_exceptions

mtu_adapter = TypeAdapter(MTU)


@pytest.mark.parametrize("mtu", (1500, 9000))
def test_mtu(mtu):
    mtu_adapter.validate_python(mtu)


def test_mtu_schema():
    assert mtu_adapter.json_schema() == {"maximum": 9000, "minimum": 1500, "multipleOf": 7500, "type": "integer"}


def test_mtu_nok_ge():
    with pytest.raises(ValidationError) as error_info:
        mtu_adapter.validate_python(1499)

    expected = [
        {
            "input": 1499,
            "ctx": {"ge": 1500},
            "loc": (),
            "msg": "Input should be greater than or equal to 1500",
            "type": "greater_than_equal",
        }
    ]
    assert error_info.value.errors(include_url=False) == expected


def test_mtu_nok_le():
    with pytest.raises(ValidationError) as error_info:
        mtu_adapter.validate_python(9001)

    expected = [
        {
            "input": 9001,
            "ctx": {"le": 9000},
            "loc": (),
            "msg": "Input should be less than or equal to 9000",
            "type": "less_than_equal",
        },
    ]
    assert error_info.value.errors(include_url=False) == expected


def test_mtu_nok_1500_or_9000():
    with pytest.raises(ValidationError) as error_info:
        mtu_adapter.validate_python(1600)

    expected = [
        {
            "input": 1600,
            "ctx": {"error": ValueError("MTU must be either 1500 or 9000")},
            "loc": (),
            "msg": "Value error, MTU must be either 1500 or 9000",
            "type": "value_error",
        },
    ]
    assert stringify_exceptions(error_info.value.errors(include_url=False)) == stringify_exceptions(expected)
