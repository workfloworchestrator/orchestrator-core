# Copyright 2019-2026 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for CLI generator validations: validation discovery, import generation, and validation list construction."""

import pytest

from orchestrator.core.cli.generator.generator.validations import (
    get_all_validations,
    get_validation_imports,
    get_validations,
)

_FIELDS_NO_VALIDATIONS = [{"name": "field1", "type": "str"}, {"name": "field2", "type": "int"}]

_FIELDS_WITH_VALIDATIONS = [
    {
        "name": "field1",
        "type": "str",
        "validations": [{"id": "min_length", "value": 1}, {"id": "max_length", "value": 10}],
    },
    {
        "name": "field2",
        "type": "int",
        "validations": [{"id": "positive"}],
    },
]

_FIELDS_MIXED_MODIFIABLE = [
    {"name": "field1", "type": "str", "modifiable": False, "validations": [{"id": "min_length"}]},
    {"name": "field2", "type": "str", "modifiable": True, "validations": [{"id": "max_length"}]},
]

_VALIDATION_ENTRIES = [
    {"validation": {"id": "min_length"}, "field": {"name": "field1"}},
    {"validation": {"id": "max_length"}, "field": {"name": "field1"}},
    {"validation": {"id": "positive"}, "field": {"name": "field2"}},
]


def test_get_all_validations_empty_fields() -> None:
    assert get_all_validations([]) == []


def test_get_all_validations_without_validations() -> None:
    assert get_all_validations(_FIELDS_NO_VALIDATIONS) == []


def test_get_all_validations_with_validations() -> None:
    result = get_all_validations(_FIELDS_WITH_VALIDATIONS)
    assert len(result) == 3
    assert result[0] == {"validation": {"id": "min_length", "value": 1}, "field": _FIELDS_WITH_VALIDATIONS[0]}
    assert result[2] == {"validation": {"id": "positive"}, "field": _FIELDS_WITH_VALIDATIONS[1]}


def test_get_validation_imports() -> None:
    result = get_validation_imports(_VALIDATION_ENTRIES)
    assert result == ["min_length_validator", "max_length_validator", "positive_validator"]


@pytest.mark.parametrize(
    "workflow,expected_count,expected_imports",
    [
        pytest.param("create", 2, ["min_length_validator", "max_length_validator"], id="create-all"),
        pytest.param("modify", 1, ["max_length_validator"], id="modify-modifiable-only"),
    ],
)
def test_get_validations(workflow: str, expected_count: int, expected_imports: list[str]) -> None:
    validations, imports = get_validations(_FIELDS_MIXED_MODIFIABLE, workflow=workflow)
    assert len(validations) == expected_count
    assert imports == expected_imports


def test_get_validations_modify_no_modifiable() -> None:
    fields = [{"name": "field1", "type": "str", "modifiable": False, "validations": [{"id": "min_length"}]}]
    validations, imports = get_validations(fields, workflow="modify")
    assert validations == []
    assert imports == []
