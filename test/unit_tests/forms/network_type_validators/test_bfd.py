import pytest
from pydantic import ValidationError

from orchestrator.forms.validators import BFD
from pydantic_forms.core import FormPage


def test_bfd_ok():
    class Form(FormPage):
        bfd: BFD

    model = {"enabled": False, "minimum_interval": None, "multiplier": None}
    validated_data = Form(bfd=model).model_dump()

    expected = {"bfd": BFD(enabled=False, minimum_interval=None, multiplier=None).model_dump()}
    assert expected == validated_data

    model = {"enabled": True, "minimum_interval": 600, "multiplier": 3}
    validated_data = Form(bfd=model).model_dump()

    expected = {"bfd": BFD(enabled=True, minimum_interval=600, multiplier=3).model_dump()}
    assert expected == validated_data


def test_bfd_schema():
    class Form(FormPage):
        bfd: BFD

    assert Form.model_json_schema() == {
        "additionalProperties": False,
        "$defs": {
            "BFD": {
                "format": "optGroup",
                "properties": {
                    "enabled": {"title": "Enabled", "type": "boolean"},
                    "minimum_interval": {
                        "anyOf": [{"maximum": 255000, "minimum": 1, "type": "integer"}, {"type": "null"}],
                        "default": 900,
                        "title": "Minimum " "Interval",
                    },
                    "multiplier": {
                        "anyOf": [{"maximum": 255, "minimum": 1, "type": "integer"}, {"type": "null"}],
                        "default": 3,
                        "title": "Multiplier",
                    },
                },
                "required": ["enabled"],
                "title": "BFD",
                "type": "object",
            }
        },
        "properties": {"bfd": {"$ref": "#/$defs/BFD"}},
        "required": ["bfd"],
        "title": "unknown",
        "type": "object",
    }


def test_bfd_enabled_missing_values():
    class Form(FormPage):
        bfd: BFD

    model = {"enabled": True, "multiplier": 4}
    assert Form(bfd=model).model_dump() == {"bfd": {"enabled": True, "multiplier": 4, "minimum_interval": 900}}

    model = {"enabled": True, "minimum_interval": 600}
    assert Form(bfd=model).model_dump() == {"bfd": {"enabled": True, "multiplier": 3, "minimum_interval": 600}}


def test_bfd_disabled_missing_values():
    class Form(FormPage):
        bfd: BFD

    model = {"enabled": False}
    assert Form(bfd=model).model_dump() == {"bfd": {"enabled": False}}

    model = {"enabled": False, "minimum_interval": 600, "multiplier": 3}
    assert Form(bfd=model).model_dump() == {"bfd": {"enabled": False}}


def test_bfd_wrong_minimum_interval_ge():
    class Form(FormPage):
        bfd: BFD

    with pytest.raises(ValidationError) as error_info:
        Form(bfd={"enabled": True, "minimum_interval": 0, "multiplier": 3})

    expected = [
        {
            "input": 0,
            "loc": ("bfd", "minimum_interval"),
            "msg": "Input should be greater than or equal to 1",
            "type": "greater_than_equal",
            "ctx": {"ge": 1},
        },
    ]
    assert error_info.value.errors(include_url=False) == expected


def test_bfd_wrong_minimum_interval_le():
    class Form(FormPage):
        bfd: BFD

    with pytest.raises(ValidationError) as error_info:
        Form(bfd={"enabled": True, "minimum_interval": 255001, "multiplier": 3})

    expected = [
        {
            "input": 255001,
            "loc": ("bfd", "minimum_interval"),
            "msg": "Input should be less than or equal to 255000",
            "type": "less_than_equal",
            "ctx": {"le": 255000},
        },
    ]
    assert error_info.value.errors(include_url=False) == expected


def test_bfd_wrong_multiplier_ge():
    class Form(FormPage):
        bfd: BFD

    with pytest.raises(ValidationError) as error_info:
        Form(bfd={"enabled": True, "minimum_interval": 600, "multiplier": 0})

    expected = [
        {
            "input": 0,
            "loc": ("bfd", "multiplier"),
            "msg": "Input should be greater than or equal to 1",
            "type": "greater_than_equal",
            "ctx": {"ge": 1},
        },
    ]
    assert error_info.value.errors(include_url=False) == expected


def test_bfd_wrong_multiplier_le():
    class Form(FormPage):
        bfd: BFD

    with pytest.raises(ValidationError) as error_info:
        Form(bfd={"enabled": True, "minimum_interval": 600, "multiplier": 256})

    expected = [
        {
            "input": 256,
            "loc": ("bfd", "multiplier"),
            "msg": "Input should be less than or equal to 255",
            "type": "less_than_equal",
            "ctx": {"le": 255},
        },
    ]
    assert error_info.value.errors(include_url=False) == expected
