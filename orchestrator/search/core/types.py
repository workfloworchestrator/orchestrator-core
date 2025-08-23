from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, NamedTuple, TypeAlias, TypedDict
from uuid import UUID

from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy_utils.types.ltree import Ltree

from .validators import is_bool_string, is_iso_date, is_uuid

SQLAColumn: TypeAlias = ColumnElement[Any] | InstrumentedAttribute[Any]


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


class EntityType(str, Enum):
    SUBSCRIPTION = "SUBSCRIPTION"
    PRODUCT = "PRODUCT"
    WORKFLOW = "WORKFLOW"
    PROCESS = "PROCESS"


class ActionType(str, Enum):
    """Defines the explicit, safe actions the agent can request."""

    SELECT = "select"  # Retrieve a list of matching records.
    # COUNT = "count"  # For phase1; the agent will not support this yet.


class UIType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATETIME = "datetime"

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

    def pg_cast(self) -> str:
        return {
            FieldType.STRING: "::text",
            FieldType.INTEGER: "::integer",
            FieldType.FLOAT: "::double precision",
            FieldType.BOOLEAN: "::boolean",
            FieldType.DATETIME: "::timestamptz",
            FieldType.UUID: "::uuid",
        }.get(self, "::text")

    def is_embeddable(self) -> bool:
        return self == FieldType.STRING


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
    path: Ltree
    value: Any
    value_type: Any
    content_hash: str
    embedding: list[float] | None
