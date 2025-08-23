from typing import Literal

from pydantic import BaseModel, ConfigDict

from orchestrator.search.core.types import FilterOp, UIType


class Highlight(BaseModel):
    """Contains the text and the indices of the matched term."""

    text: str
    indices: list[tuple[int, int]]


class SearchResult(BaseModel):
    """Represents a single search result item."""

    entity_id: str
    score: float
    highlight: Highlight | None = None


SearchResponse = list[SearchResult]


class ValueSchema(BaseModel):
    kind: UIType | Literal["none", "object"] = UIType.STRING
    fields: dict[str, "ValueSchema"] | None = None

    model_config = ConfigDict(extra="forbid")


class PathInfo(BaseModel):
    path: str
    type: UIType

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
    )


class TypeDefinition(BaseModel):
    operators: list[FilterOp]
    valueSchema: dict[FilterOp, ValueSchema]

    model_config = ConfigDict(use_enum_values=True)
