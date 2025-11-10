# Copyright 2019-2025 SURF, GÉANT.
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

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, IntEnum
from typing import Annotated, Any, Literal, NamedTuple, TypeAlias, TypedDict, get_args, get_origin
from uuid import UUID

from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.types import filter_nonetype, get_origin_and_args, is_optional_type, is_union_type

from .validators import is_bool_string, is_iso_date, is_uuid

SQLAColumn: TypeAlias = ColumnElement[Any] | InstrumentedAttribute[Any]

LTREE_SEPARATOR = "."


@dataclass
class SearchMetadata:
    """Metadata about the search operation performed."""

    search_type: str
    description: str

    @classmethod
    def structured(cls) -> "SearchMetadata":
        return cls(
            search_type="structured", description="This search performs a filter-based search using structured queries."
        )

    @classmethod
    def fuzzy(cls) -> "SearchMetadata":
        return cls(
            search_type="fuzzy",
            description="This search performs a trigram similarity search.",
        )

    @classmethod
    def semantic(cls) -> "SearchMetadata":
        return cls(
            search_type="semantic",
            description="This search performs a vector similarity search, using L2 distance on embeddings with minimum distance scoring (normalized).",
        )

    @classmethod
    def hybrid(cls) -> "SearchMetadata":
        return cls(
            search_type="hybrid",
            description="This search performs reciprocal rank fusion combining trigram similarity, word_similarity, and L2 vector distance.",
        )

    @classmethod
    def empty(cls) -> "SearchMetadata":
        return cls(search_type="empty", description="Empty search - no criteria provided")


class BooleanOperator(str, Enum):
    AND = "AND"
    OR = "OR"


class FilterOp(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    LT = "lt"
    LIKE = "like"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    BETWEEN = "between"

    MATCHES_LQUERY = "matches_lquery"  # The ~ operator for wildcard matching
    IS_ANCESTOR = "is_ancestor"  # The @> operator
    IS_DESCENDANT = "is_descendant"  # The <@ operator
    PATH_MATCH = "path_match"

    HAS_COMPONENT = "has_component"  # Path contains this segment
    NOT_HAS_COMPONENT = "not_has_component"  # Path doesn't contain segment
    ENDS_WITH = "ends_with"


class EntityType(str, Enum):
    SUBSCRIPTION = "SUBSCRIPTION"
    PRODUCT = "PRODUCT"
    WORKFLOW = "WORKFLOW"
    PROCESS = "PROCESS"


class ActionType(str, Enum):
    """Defines the explicit, safe actions the agent can request."""

    SELECT = "select"  # Retrieve a list of matching records.
    COUNT = "count"  # Count matching records, optionally grouped.
    AGGREGATE = "aggregate"  # Compute aggregations (sum, avg, etc.) over matching records.


class UIType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    COMPONENT = "component"

    @classmethod
    def from_field_type(cls, ft: "FieldType") -> "UIType":
        """Create a UIType from a backend FieldType to indicate how a value must be rendered."""
        if ft in (FieldType.INTEGER, FieldType.FLOAT):
            return cls.NUMBER
        if ft == FieldType.BOOLEAN:
            return cls.BOOLEAN
        if ft == FieldType.DATETIME:
            return cls.DATETIME
        return cls.STRING


class FieldType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    UUID = "uuid"
    BLOCK = "block"
    RESOURCE_TYPE = "resource_type"

    @classmethod
    def infer(cls, val: Any) -> "FieldType":
        if isinstance(val, TypedValue):
            return cls._infer_typed_value(val)

        if isinstance(val, bool):
            return cls.BOOLEAN
        if isinstance(val, int):
            return cls.INTEGER
        if isinstance(val, float):
            return cls.FLOAT
        if isinstance(val, UUID):
            return cls.UUID
        if isinstance(val, (datetime, date)):
            return cls.DATETIME
        if isinstance(val, str):
            return cls._infer_from_str(val)

        return cls.STRING

    @classmethod
    def _infer_typed_value(cls, val: "TypedValue") -> "FieldType":
        if val.type == cls.BLOCK:
            return cls.BLOCK
        if val.type == cls.RESOURCE_TYPE:
            return cls.RESOURCE_TYPE
        return cls.STRING

    @classmethod
    def _infer_from_str(cls, val: str) -> "FieldType":
        if is_uuid(val):
            return cls.UUID
        if is_iso_date(val):
            return cls.DATETIME
        if is_bool_string(val):
            return cls.BOOLEAN
        if val.isdigit():
            return cls.INTEGER
        try:
            float(val)
            return cls.FLOAT
        except ValueError:
            return cls.STRING

    @classmethod
    def from_type_hint(cls, type_hint: object) -> "FieldType":
        """Convert type hint to FieldType."""
        _type_mapping = {
            int: cls.INTEGER,
            float: cls.FLOAT,
            bool: cls.BOOLEAN,
            str: cls.STRING,
            datetime: cls.DATETIME,
            UUID: cls.UUID,
        }

        if type_hint in _type_mapping:
            return _type_mapping[type_hint]  # type: ignore[index]

        if get_origin(type_hint) is Annotated:
            inner_type = get_args(type_hint)[0]
            return cls.from_type_hint(inner_type)

        origin, args = get_origin_and_args(type_hint)

        if origin is list:
            return cls._handle_list_type(args)

        if origin is Literal:
            return cls._handle_literal_type(args)

        if is_optional_type(type_hint) or is_union_type(type_hint):
            return cls._handle_union_type(args)

        if isinstance(type_hint, type):
            return cls._handle_class_type(type_hint)

        return cls.STRING

    @classmethod
    def _handle_list_type(cls, args: tuple) -> "FieldType":
        if args:
            element_type = args[0]
            return cls.from_type_hint(element_type)
        return cls.STRING

    @classmethod
    def _handle_literal_type(cls, args: tuple) -> "FieldType":
        if not args:
            return cls.STRING
        first_value = args[0]
        if isinstance(first_value, bool):
            return cls.BOOLEAN
        if isinstance(first_value, int):
            return cls.INTEGER
        if isinstance(first_value, str):
            return cls.STRING
        if isinstance(first_value, float):
            return cls.FLOAT
        return cls.STRING

    @classmethod
    def _handle_union_type(cls, args: tuple) -> "FieldType":
        non_none_types = list(filter_nonetype(args))
        if non_none_types:
            return cls.from_type_hint(non_none_types[0])
        return cls.STRING

    @classmethod
    def _handle_class_type(cls, type_hint: type) -> "FieldType":
        if issubclass(type_hint, IntEnum):
            return cls.INTEGER
        if issubclass(type_hint, Enum):
            return cls.STRING

        from orchestrator.domain.base import ProductBlockModel

        if issubclass(type_hint, ProductBlockModel):
            return cls.BLOCK

        return cls.STRING

    def is_embeddable(self, value: str | None) -> bool:
        """Check if a field should be embedded."""
        if value is None or value == "":
            return False

        # If inference suggests it's not actually a string, don't embed it
        return FieldType._infer_from_str(value) == FieldType.STRING


@dataclass(frozen=True)
class TypedValue:
    value: Any
    type: FieldType


class ExtractedField(NamedTuple):
    path: str
    value: str
    value_type: FieldType

    @classmethod
    def from_raw(cls, path: str, raw_value: Any) -> "ExtractedField":
        value = str(raw_value.value if isinstance(raw_value, TypedValue) else raw_value)
        value_type = FieldType.infer(raw_value)
        return cls(path=path, value=value, value_type=value_type)


class IndexableRecord(TypedDict):
    entity_id: str
    entity_type: str
    entity_title: str
    path: Ltree
    value: Any
    value_type: Any
    content_hash: str
    embedding: list[float] | None
