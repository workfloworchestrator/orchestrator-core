import pytest
from pydantic import ValidationError

from nwastdlib.vlans import VlanRanges
from orchestrator.forms.network_type_validators import VlanRangesValidator
from pydantic_forms.core import FormPage


@pytest.mark.parametrize(
    "vlanranges, expected",
    [
        (4096, 4096),
        (0, 0),
        ("0-4096", "0-4096"),
        ("1,2,3", "1,2,3"),
        ("1,1,1", "1"),
    ],
)
def test_vlanranges(vlanranges, expected):
    class Form(FormPage):
        vlanranges: VlanRangesValidator

    assert Form(vlanranges=vlanranges).vlanranges == VlanRanges(expected)


def test_vlanranges_schema():
    class Form(FormPage):
        vlanranges: VlanRangesValidator

    assert Form.model_json_schema() == {
        "additionalProperties": False,
        "properties": {
            "vlanranges": {
                "examples": ["345", "20-23,45,50-100"],
                "format": "vlan",
                "pattern": "^([1-4][0-9]{0,3}(-[1-4][0-9]{0,3})?,?)+$",
                "title": "Vlanranges",
                "type": "string",
            }
        },
        "required": ["vlanranges"],
        "title": "unknown",
        "type": "object",
    }


@pytest.mark.parametrize(
    "vlanranges, expected_msg",
    [
        ("4097", "Value error, 4097 is out of range (0-4096)."),
        (-1, "Value error, -1 is out of range (0-4096)."),
        ("a,b,c", "Value error, a,b,c could not be converted to a _VlanRanges object."),
    ],
)
def test_vlanranges_nok(vlanranges, expected_msg):
    class Form(FormPage):
        vlanranges: VlanRangesValidator

    with pytest.raises(ValidationError) as error_info:
        assert Form(vlanranges=vlanranges)

    expected = [
        {"input": vlanranges, "loc": ("vlanranges",), "msg": expected_msg, "type": "value_error"},
    ]
    assert error_info.value.errors(include_context=False, include_url=False) == expected
