from enum import Enum
from typing import Any, NamedTuple, Type, TYPE_CHECKING
from uuid import UUID
from datetime import datetime, date
from .validators import is_uuid, is_iso_date, is_bool_string
from dataclasses import dataclass
from orchestrator.db.database import BaseModel

if TYPE_CHECKING:
    from search.indexing.traverse import BaseTraverser


class EntityKind(str, Enum):
    SUBSCRIPTION = "SUBSCRIPTION"
    PRODUCT = "PRODUCT"
    WORKFLOW = "WORKFLOW"
    PROCESS = "PROCESS"


class ActionType(str, Enum):
    """Defines the explicit, safe actions the agent can request."""

    SELECT = "select"  # Retrieve a list of matching records.
    # COUNT = "count"  # For phase1; the search bar will not support this yet.


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
            if val.type == cls.BLOCK:
                return cls.BLOCK
            elif val.type == cls.RESOURCE_TYPE:
                return cls.RESOURCE_TYPE

        elif isinstance(val, bool):
            return cls.BOOLEAN
        elif isinstance(val, int):
            return cls.INTEGER
        elif isinstance(val, float):
            return cls.FLOAT
        elif isinstance(val, UUID):
            return cls.UUID
        elif isinstance(val, (datetime, date)):
            return cls.DATETIME
        elif isinstance(val, str):
            if is_uuid(val):
                return cls.UUID
            elif is_iso_date(val):
                return cls.DATETIME
            elif is_bool_string(val):
                return cls.BOOLEAN
            elif val.isdigit():
                return cls.INTEGER
            else:
                try:
                    float(val)
                    return cls.FLOAT
                except ValueError:
                    pass
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


@dataclass(frozen=True)
class EntityConfig:
    """A container for all configuration related to a specific entity type."""

    entity_kind: EntityKind
    table: Type[BaseModel]
    traverser: "Type[BaseTraverser]"
    pk_name: str
    root_name: str
