"""Tests for CLI generator helpers: path resolution, template rendering, and file generation."""

from pathlib import Path
from typing import Any

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
    "config,expected",
    [
        pytest.param({"variable": "my_var", "name": "MyProduct"}, "my_var", id="explicit-variable"),
        pytest.param({"name": "MyProduct"}, "my_product", id="camel-to-snake"),
        pytest.param({"name": "MyProductBlock"}, "my_product_block", id="complex-name"),
    ],
)
def test_get_variable(config: dict, expected: str) -> None:
    assert get_variable(config) == expected


@pytest.mark.parametrize(
    "block_name,expected",
    [
        pytest.param("PortBlock", "Port", id="simple"),
        pytest.param("PortBlockInactive", "Port", id="with-lifecycle"),
        pytest.param("SomeComplexBlock", "SomeComplex", id="complex"),
        pytest.param("SomeComplexBlockActive", "SomeComplex", id="complex-lifecycle"),
    ],
)
def test_base_block_type(block_name: str, expected: str) -> None:
    assert base_block_type(block_name) == expected


_ROOT_AND_CHILD: list[dict[str, Any]] = [
    {"type": "Root", "fields": [{"name": "child", "type": "Child"}]},
    {"type": "Child", "fields": []},
]

_CYCLIC_BLOCKS: list[dict[str, Any]] = [
    {"type": "A", "fields": [{"name": "b", "type": "B"}]},
    {"type": "B", "fields": [{"name": "a", "type": "A"}]},
]

_TWO_ROOTS: list[dict[str, Any]] = [
    {"type": "RootA", "fields": []},
    {"type": "RootB", "fields": []},
]


def test_find_root_product_block_single() -> None:
    assert find_root_product_block(_ROOT_AND_CHILD) == "Root"


def test_find_root_product_block_none() -> None:
    with pytest.raises(ValueError, match="exactly 1 root product block, found none"):
        find_root_product_block(_CYCLIC_BLOCKS)


def test_find_root_product_block_multiple() -> None:
    with pytest.raises(ValueError, match="exactly 1 root product block, found multiple"):
        find_root_product_block(_TWO_ROOTS)


def test_sort_product_blocks_by_dependencies_simple() -> None:
    result = sort_product_blocks_by_dependencies(_ROOT_AND_CHILD)
    types = [b["type"] for b in result]
    assert types.index("Child") < types.index("Root")


def test_sort_product_blocks_by_dependencies_cycle() -> None:
    with pytest.raises(ValueError, match="Cycle detected in product blocks"):
        sort_product_blocks_by_dependencies(_CYCLIC_BLOCKS)


def test_insert_into_imports_before_first_from() -> None:
    content = ["import os", "from pathlib import Path", "x = 1"]
    result = insert_into_imports(content, "from mymodule import something")
    assert result == ["import os", "from mymodule import something", "from pathlib import Path", "x = 1"]


def test_insert_into_imports_no_from() -> None:
    content = ["import os", "import sys", "x = 1"]
    result = insert_into_imports(content, "from mymodule import something")
    assert result == ["import os", "import sys", "x = 1"]


def test_path_to_module() -> None:
    assert path_to_module(Path("orchestrator/cli/generator")) == "orchestrator.cli.generator"


@pytest.mark.parametrize(
    "field,expected",
    [
        pytest.param({"name": "count", "type": "int", "min_value": 0}, True, id="min-only"),
        pytest.param({"name": "count", "type": "int", "max_value": 100}, True, id="max-only"),
        pytest.param({"name": "count", "type": "int", "min_value": 0, "max_value": 100}, True, id="both"),
        pytest.param({"name": "label", "type": "str"}, False, id="non-int"),
        pytest.param({"name": "x", "type": "int"}, False, id="no-constraints"),
    ],
)
def test_is_constrained_int(field: dict, expected: bool) -> None:
    assert is_constrained_int(field) == expected


_MIXED_FIELDS: list[dict[str, Any]] = [
    {"name": "count", "type": "int", "min_value": 0},
    {"name": "label", "type": "str"},
    {"name": "size", "type": "int", "max_value": 100},
]


def test_get_constrained_ints() -> None:
    result = get_constrained_ints(_MIXED_FIELDS)
    assert [r["name"] for r in result] == ["count", "size"]


_MERGE_FIELDS: list[dict[str, Any]] = [{"name": "alpha", "type": "str"}, {"name": "beta", "type": "int"}]
_MERGE_INT_ENUMS: list[dict[str, Any]] = [{"name": "gamma", "type": "IntEnum"}]
_MERGE_STR_ENUMS: list[dict[str, Any]] = [{"name": "beta", "type": "StrEnum"}]


def test_merge_fields() -> None:
    result = merge_fields(_MERGE_FIELDS, _MERGE_INT_ENUMS, _MERGE_STR_ENUMS)
    result_by_name = {r["name"]: r for r in result}
    assert result_by_name["alpha"]["type"] == "str"
    assert result_by_name["beta"]["type"] == "StrEnum"
    assert result_by_name["gamma"]["type"] == "IntEnum"


@pytest.mark.parametrize(
    "field,expected_type",
    [
        pytest.param({"name": "my_count", "type": "int", "min_value": 0}, "MyCount", id="constrained-min"),
        pytest.param({"name": "some_value", "type": "int", "max_value": 50}, "SomeValue", id="constrained-max"),
        pytest.param({"name": "vlan", "type": "some.module.VlanType"}, "VlanType", id="namespaced"),
        pytest.param({"name": "label", "type": "str"}, "str", id="regular"),
    ],
)
def test_process_fields(field: dict, expected_type: str) -> None:
    result = process_fields([field])
    assert result[0]["type"] == expected_type


_NAMESPACED_FIELDS: list[dict[str, Any]] = [
    {"name": "vlan", "type": "some.module.VlanType"},
    {"name": "label", "type": "str"},
    {"name": "speed", "type": "network.Speed"},
]


def test_get_name_spaced_types_to_import() -> None:
    result = get_name_spaced_types_to_import(_NAMESPACED_FIELDS)
    assert len(result) == 2
    assert ("some.module", "VlanType") in result
    assert ("network", "Speed") in result


def test_get_name_spaced_types_to_import_none() -> None:
    result = get_name_spaced_types_to_import([{"name": "label", "type": "str"}])
    assert result == []
