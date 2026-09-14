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

"""The indexed value_type must describe the value actually stored, not just its annotation.

`FieldType.from_type_hint` reads the Pydantic annotation, which can disagree with the
runtime value: a union records its first non-None member regardless of which member the
value belongs to, and a computed field's declared return type is never validated by
Pydantic. A row whose value_type contradicts its value breaks every downstream consumer
that trusts the column -- `_restore_value_type` raises on `int("untagged")`, numeric
filters emit a Postgres cast over non-numeric text, and `ai_search_paths` advertises the
wrong UI type.
"""

from typing import Literal

import pytest
from pydantic import BaseModel, computed_field

from orchestrator.core.search.core.types import FieldType
from orchestrator.core.search.indexing.traverse import BaseTraverser


class _Traverser(BaseTraverser):
    """Concrete traverser: these tests drive `traverse` directly, never `_load_model`."""

    @classmethod
    def _load_model(cls, entity: object) -> object:
        return entity


def _value_type_of(instance: BaseModel, field_name: str) -> FieldType:
    """Return the value_type the traverser emits for a single field of an instance."""
    fields = {field.path: field for field in _Traverser.traverse(instance, path="subscription")}
    return fields[f"subscription.{field_name}"].value_type


class UnionBlock(BaseModel):
    """Union-annotated fields whose value may belong to either member."""

    int_first: int | str = 0
    str_first: str | int = ""
    float_first: float | str = 0.0
    bool_first: bool | str = False
    literal_int_first: Literal[1500, "untagged"] = 1500


class ComputedBlock(BaseModel):
    """Computed fields whose declared return type Pydantic never enforces."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def declared_int(self) -> int:
        return "unknown"  # type: ignore[return-value]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def declared_float(self) -> float:
        return "n/a"  # type: ignore[return-value]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def declared_bool(self) -> bool:
        return "maybe"  # type: ignore[return-value]


@pytest.mark.parametrize(
    ("field_name", "value", "expected_value_type"),
    [
        pytest.param("int_first", "untagged", FieldType.STRING, id="int-union-holding-string"),
        pytest.param("int_first", 100, FieldType.INTEGER, id="int-union-holding-int"),
        # A str-annotated field holding digits stays a string: text represents any value,
        # so the annotation is never wrong and `customer_id: str = "12345"` keeps its type.
        pytest.param("str_first", 100, FieldType.STRING, id="str-union-holding-int"),
        pytest.param("str_first", "untagged", FieldType.STRING, id="str-union-holding-string"),
        pytest.param("float_first", "unmetered", FieldType.STRING, id="float-union-holding-string"),
        pytest.param("float_first", 0.5, FieldType.FLOAT, id="float-union-holding-float"),
        pytest.param("bool_first", "unknown", FieldType.STRING, id="bool-union-holding-string"),
        pytest.param("literal_int_first", "untagged", FieldType.STRING, id="literal-union-holding-string"),
    ],
)
def test_union_field_value_type_matches_stored_value(field_name, value, expected_value_type):
    """A union field whose value its first member cannot represent is indexed by the value."""
    assert _value_type_of(UnionBlock(**{field_name: value}), field_name) == expected_value_type


@pytest.mark.parametrize(
    ("field_name", "expected_value_type"),
    [
        pytest.param("declared_int", FieldType.STRING, id="declared-int-returning-string"),
        pytest.param("declared_float", FieldType.STRING, id="declared-float-returning-string"),
        pytest.param("declared_bool", FieldType.STRING, id="declared-bool-returning-string"),
    ],
)
def test_computed_field_value_type_matches_returned_value(field_name, expected_value_type):
    """A computed field is indexed as the type it returns; Pydantic never checks the annotation."""
    assert _value_type_of(ComputedBlock(), field_name) == expected_value_type
