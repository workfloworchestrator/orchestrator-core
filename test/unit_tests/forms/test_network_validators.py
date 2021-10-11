import pytest
from pydantic import ValidationError

from orchestrator.forms import FormPage
from orchestrator.forms.network_type_validators import BFD, MTU, VlanRangesValidator
from orchestrator.utils.vlans import VlanRanges


def test_bfd_ok():
    class Form(FormPage):
        bfd: BFD

    model = {"enabled": False, "minimum_interval": None, "multiplier": None}
    validated_data = Form(bfd=model).dict()

    expected = {"bfd": BFD(enabled=False, minimum_interval=None, multiplier=None)}
    assert expected == validated_data

    model = {"enabled": True, "minimum_interval": 600, "multiplier": 3}
    validated_data = Form(bfd=model).dict()

    expected = {"bfd": BFD(enabled=True, minimum_interval=600, multiplier=3)}
    assert expected == validated_data


def test_bfd_schema():
    class Form(FormPage):
        bfd: BFD

    assert Form.schema() == {
        "additionalProperties": False,
        "definitions": {
            "BFD": {
                "format": "optGroup",
                "properties": {
                    "enabled": {"title": "Enabled", "type": "boolean"},
                    "minimum_interval": {
                        "default": 900,
                        "maximum": 255000,
                        "minimum": 1,
                        "title": "Minimum " "Interval",
                        "type": "integer",
                    },
                    "multiplier": {
                        "default": 3,
                        "maximum": 255,
                        "minimum": 1,
                        "title": "Multiplier",
                        "type": "integer",
                    },
                },
                "required": ["enabled"],
                "title": "BFD",
                "type": "object",
            }
        },
        "properties": {"bfd": {"$ref": "#/definitions/BFD"}},
        "required": ["bfd"],
        "title": "unknown",
        "type": "object",
    }


def test_bfd_missing_values():
    class Form(FormPage):
        bfd: BFD

    model = {"enabled": False}
    assert Form(bfd=model).dict() == {"bfd": {"enabled": False}}

    model = {"enabled": True, "multiplier": 4}
    assert Form(bfd=model).dict() == {"bfd": {"enabled": True, "multiplier": 4, "minimum_interval": 900}}

    model = {"enabled": True, "minimum_interval": 600}
    assert Form(bfd=model).dict() == {"bfd": {"enabled": True, "multiplier": 3, "minimum_interval": 600}}

    model = {"enabled": False, "minimum_interval": 600, "multiplier": 3}
    assert Form(bfd=model).dict() == {"bfd": {"enabled": False}}


def test_bfd_wrong_values():
    class Form(FormPage):
        bfd: BFD

    with pytest.raises(ValidationError) as error_info:
        Form(bfd={"enabled": True, "minimum_interval": 0, "multiplier": 3})

    expected = [
        {
            "loc": ("bfd", "minimum_interval"),
            "msg": "ensure this value is greater than or equal to 1",
            "type": "value_error.number.not_ge",
            "ctx": {"limit_value": 1},
        },
    ]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        Form(bfd={"enabled": True, "minimum_interval": 255001, "multiplier": 3})

    expected = [
        {
            "loc": ("bfd", "minimum_interval"),
            "msg": "ensure this value is less than or equal to 255000",
            "type": "value_error.number.not_le",
            "ctx": {"limit_value": 255000},
        },
    ]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        Form(bfd={"enabled": True, "minimum_interval": 600, "multiplier": 0})

    expected = [
        {
            "loc": ("bfd", "multiplier"),
            "msg": "ensure this value is greater than or equal to 1",
            "type": "value_error.number.not_ge",
            "ctx": {"limit_value": 1},
        },
    ]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        Form(bfd={"enabled": True, "minimum_interval": 600, "multiplier": 256})

    expected = [
        {
            "loc": ("bfd", "multiplier"),
            "msg": "ensure this value is less than or equal to 255",
            "type": "value_error.number.not_le",
            "ctx": {"limit_value": 255},
        },
    ]
    assert expected == error_info.value.errors()


def test_mtu():
    class Form(FormPage):
        mtu: MTU

    assert Form(mtu=1500).mtu == 1500
    assert Form(mtu=1501).mtu == 1501
    assert Form(mtu=9000).mtu == 9000


def test_mtu_schema():
    class Form(FormPage):
        mtu: MTU

    assert Form.schema() == {
        "additionalProperties": False,
        "properties": {
            "mtu": {"maximum": 9000, "minimum": 1500, "multipleOf": 7500, "title": "Mtu", "type": "integer"}
        },
        "required": ["mtu"],
        "title": "unknown",
        "type": "object",
    }


def test_mtu_nok():
    class Form(FormPage):
        mtu: MTU

    with pytest.raises(ValidationError) as error_info:
        assert Form(mtu=1499)

    expected = [
        {
            "ctx": {"limit_value": 1500},
            "loc": ("mtu",),
            "msg": "ensure this value is greater than or equal to 1500",
            "type": "value_error.number.not_ge",
        }
    ]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        assert Form(mtu=9001)

    expected = [
        {
            "ctx": {"limit_value": 9000},
            "loc": ("mtu",),
            "msg": "ensure this value is less than or equal to 9000",
            "type": "value_error.number.not_le",
        },
    ]
    assert expected == error_info.value.errors()


def test_vlanranges():
    class Form(FormPage):
        vlanranges: VlanRangesValidator

    assert Form(vlanranges=4096).vlanranges == VlanRanges(4096)
    assert Form(vlanranges=0).vlanranges == VlanRanges(0)
    assert Form(vlanranges="0-4096").vlanranges == VlanRanges("0-4096")
    assert Form(vlanranges="1,2,3").vlanranges == VlanRanges("1,2,3")
    assert Form(vlanranges="1,1,1").vlanranges == VlanRanges("1")


def test_vlanranges_schema():
    class Form(FormPage):
        vlanranges: VlanRangesValidator

    assert Form.schema() == {
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


def test_vlanranges_nok():
    class Form(FormPage):
        vlanranges: VlanRangesValidator

    with pytest.raises(ValidationError) as error_info:
        assert Form(vlanranges="4097")

    expected = [
        {"loc": ("vlanranges",), "msg": "4097 is out of range (0-4096).", "type": "value_error"},
    ]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        assert Form(vlanranges=-1)

    expected = [
        {"loc": ("vlanranges",), "msg": "-1 is out of range (0-4096).", "type": "value_error"},
    ]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        assert Form(vlanranges="a,b,c")

    expected = [
        {"loc": ("vlanranges",), "msg": "a,b,c could not be converted to a VlanRanges object.", "type": "value_error"},
    ]
    assert expected == error_info.value.errors()
