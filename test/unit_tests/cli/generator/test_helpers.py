from pathlib import Path

import pytest

from orchestrator.cli.generator.generator.helpers import (
    base_block_type,
    find_root_product_block,
    get_constrained_ints,
    get_name_spaced_types_to_import,
    get_variable,
    insert_into_imports,
    is_constrained_int,
    merge_fields,
    path_to_module,
    process_fields,
    sort_product_blocks_by_dependencies,
)


@pytest.mark.parametrize(
    "config, expected",
    [
        ({"variable": "my_var", "name": "MyProduct"}, "my_var"),
        ({"name": "MyProduct"}, "my_product"),
        ({"name": "SomeComplexName"}, "some_complex_name"),
    ],
)
def test_get_variable(config: dict, expected: str) -> None:
    assert get_variable(config) == expected


def test_get_variable_with_variable_key() -> None:
    config = {"variable": "custom_var", "name": "SomeName"}
    assert get_variable(config) == "custom_var"


def test_get_variable_fallback_to_camel_to_snake() -> None:
    config = {"name": "MyProductBlock"}
    assert get_variable(config) == "my_product_block"


@pytest.mark.parametrize(
    "block_name, expected",
    [
        ("PortBlock", "Port"),
        ("PortBlockInactive", "Port"),
        ("SomeComplexBlock", "SomeComplex"),
        ("SomeComplexBlockActive", "SomeComplex"),
    ],
)
def test_base_block_type(block_name: str, expected: str) -> None:
    assert base_block_type(block_name) == expected


def test_base_block_type_simple() -> None:
    assert base_block_type("PortBlock") == "Port"


def test_base_block_type_with_lifecycle() -> None:
    assert base_block_type("PortBlockInactive") == "Port"


def test_find_root_product_block_single() -> None:
    product_blocks = [
        {"type": "Root", "fields": [{"name": "child", "type": "Child"}]},
        {"type": "Child", "fields": []},
    ]
    assert find_root_product_block(product_blocks) == "Root"


def test_find_root_product_block_none() -> None:
    # Two blocks that depend on each other — cycle, no root
    product_blocks = [
        {"type": "A", "fields": [{"name": "b", "type": "B"}]},
        {"type": "B", "fields": [{"name": "a", "type": "A"}]},
    ]
    with pytest.raises(ValueError, match="exactly 1 root product block, found none"):
        find_root_product_block(product_blocks)


def test_find_root_product_block_multiple() -> None:
    # Two independent root blocks
    product_blocks = [
        {"type": "RootA", "fields": []},
        {"type": "RootB", "fields": []},
    ]
    with pytest.raises(ValueError, match="exactly 1 root product block, found multiple"):
        find_root_product_block(product_blocks)


def test_sort_product_blocks_by_dependencies_simple() -> None:
    product_blocks = [
        {"type": "Root", "fields": [{"name": "child", "type": "Child"}]},
        {"type": "Child", "fields": []},
    ]
    result = sort_product_blocks_by_dependencies(product_blocks)
    types = [b["type"] for b in result]
    # Child has no dependencies so it comes first
    assert types.index("Child") < types.index("Root")


def test_sort_product_blocks_by_dependencies_cycle() -> None:
    product_blocks = [
        {"type": "A", "fields": [{"name": "b", "type": "B"}]},
        {"type": "B", "fields": [{"name": "a", "type": "A"}]},
    ]
    with pytest.raises(ValueError, match="Cycle detected in product blocks"):
        sort_product_blocks_by_dependencies(product_blocks)


def test_insert_into_imports_before_first_from() -> None:
    content = ["import os", "from pathlib import Path", "x = 1"]
    result = insert_into_imports(content, "from mymodule import something")
    assert result == ["import os", "from mymodule import something", "from pathlib import Path", "x = 1"]


def test_insert_into_imports_no_from() -> None:
    content = ["import os", "import sys", "x = 1"]
    result = insert_into_imports(content, "from mymodule import something")
    assert result == ["import os", "import sys", "x = 1"]


def test_path_to_module() -> None:
    p = Path("orchestrator/cli/generator")
    assert path_to_module(p) == "orchestrator.cli.generator"


@pytest.mark.parametrize(
    "field, expected",
    [
        ({"name": "count", "type": "int", "min_value": 0}, True),
        ({"name": "count", "type": "int", "max_value": 100}, True),
        ({"name": "count", "type": "int", "min_value": 0, "max_value": 100}, True),
        ({"name": "label", "type": "str"}, False),
    ],
)
def test_is_constrained_int(field: dict, expected: bool) -> None:
    assert is_constrained_int(field) == expected


def test_is_constrained_int_with_min() -> None:
    assert is_constrained_int({"name": "x", "type": "int", "min_value": 0}) is True


def test_is_constrained_int_with_max() -> None:
    assert is_constrained_int({"name": "x", "type": "int", "max_value": 10}) is True


def test_is_constrained_int_without() -> None:
    assert is_constrained_int({"name": "x", "type": "int"}) is False


def test_get_constrained_ints() -> None:
    fields = [
        {"name": "count", "type": "int", "min_value": 0},
        {"name": "label", "type": "str"},
        {"name": "size", "type": "int", "max_value": 100},
    ]
    result = get_constrained_ints(fields)
    assert len(result) == 2
    assert result[0]["name"] == "count"
    assert result[1]["name"] == "size"


def test_merge_fields() -> None:
    fields = [{"name": "alpha", "type": "str"}, {"name": "beta", "type": "int"}]
    int_enums = [{"name": "gamma", "type": "IntEnum"}]
    str_enums = [{"name": "beta", "type": "StrEnum"}]  # overlaps with fields — str_enum wins
    result = merge_fields(fields, int_enums, str_enums)
    result_by_name = {r["name"]: r for r in result}
    assert result_by_name["alpha"]["type"] == "str"
    assert result_by_name["beta"]["type"] == "StrEnum"
    assert result_by_name["gamma"]["type"] == "IntEnum"


@pytest.mark.parametrize(
    "field, expected_type",
    [
        ({"name": "my_count", "type": "int", "min_value": 0}, "MyCount"),
        ({"name": "some_value", "type": "int", "max_value": 50}, "SomeValue"),
    ],
)
def test_process_fields_constrained_int(field: dict, expected_type: str) -> None:
    result = process_fields([field])
    assert result[0]["type"] == expected_type


def test_process_fields_namespaced() -> None:
    field = {"name": "vlan", "type": "some.module.VlanType"}
    result = process_fields([field])
    assert result[0]["type"] == "VlanType"


def test_process_fields_regular() -> None:
    field = {"name": "label", "type": "str"}
    result = process_fields([field])
    assert result[0]["type"] == "str"


def test_get_name_spaced_types_to_import() -> None:
    fields = [
        {"name": "vlan", "type": "some.module.VlanType"},
        {"name": "label", "type": "str"},
        {"name": "speed", "type": "network.Speed"},
    ]
    result = get_name_spaced_types_to_import(fields)
    assert len(result) == 2
    assert ("some.module", "VlanType") in result
    assert ("network", "Speed") in result


def test_get_name_spaced_types_to_import_no_namespaced() -> None:
    fields = [
        {"name": "label", "type": "str"},
        {"name": "count", "type": "int"},
    ]
    result = get_name_spaced_types_to_import(fields)
    assert result == []
