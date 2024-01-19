import pytest
from pydantic import ValidationError

from orchestrator.forms.validators import MTU
from pydantic_forms.core import FormPage


@pytest.mark.parametrize("mtu", [1500, 1501, 9000])
def test_mtu(mtu):
    class Form(FormPage):
        mtu: MTU

    assert Form(mtu=mtu).mtu == mtu


def test_mtu_schema():
    class Form(FormPage):
        mtu: MTU

    assert Form.model_json_schema() == {
        "additionalProperties": False,
        "properties": {
            "mtu": {"maximum": 9000, "minimum": 1500, "multipleOf": 7500, "title": "Mtu", "type": "integer"}
        },
        "required": ["mtu"],
        "title": "unknown",
        "type": "object",
    }


def test_mtu_nok_ge():
    class Form(FormPage):
        mtu: MTU

    with pytest.raises(ValidationError) as error_info:
        assert Form(mtu=1499)

    expected = [
        {
            "input": 1499,
            "ctx": {"ge": 1500},
            "loc": ("mtu",),
            "msg": "Input should be greater than or equal to 1500",
            "type": "greater_than_equal",
        }
    ]
    assert error_info.value.errors(include_url=False) == expected


def test_mtu_nok_le():
    class Form(FormPage):
        mtu: MTU

    with pytest.raises(ValidationError) as error_info:
        assert Form(mtu=9001)

    expected = [
        {
            "input": 9001,
            "ctx": {"le": 9000},
            "loc": ("mtu",),
            "msg": "Input should be less than or equal to 9000",
            "type": "less_than_equal",
        },
    ]
    assert error_info.value.errors(include_url=False) == expected
