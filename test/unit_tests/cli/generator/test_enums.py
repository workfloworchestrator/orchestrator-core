from orchestrator.cli.generator.generator.enums import convert_int_enum, convert_str_enum


def test_convert_str_enum():
    field = {
        "default": "tagged",
        "enum_type": "str",
        "name": "port_mode",
        "type": "enum",
        "values": ["untagged", "tagged", "link_member"],
    }
    converted_field = convert_str_enum(field)
    assert converted_field["type"] == "PortMode"
    assert converted_field["default"] == "PortMode.tagged"


def test_convert_int_enum():
    field = {
        "default": 40000,
        "enum_type": "int",
        "name": "speed",
        "type": "enum",
        "values": [1000, 10000, 40000, 100000],
    }
    converted_field = convert_int_enum(field)
    assert converted_field["type"] == "Speed"
    assert converted_field["default"] == "Speed._40000"
