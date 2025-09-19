from typing import Literal

from pydantic import BaseModel, ConfigDict

from orchestrator.search.core.types import FilterOp, SearchMetadata, UIType


class MatchingField(BaseModel):
    """Contains the field that contributed most to the (fuzzy) search result."""

    text: str
    path: str
    highlight_indices: list[tuple[int, int]] | None = None


class SearchResult(BaseModel):
    """Represents a single search result item."""

    entity_id: str
    score: float
    perfect_match: int = 0
    matching_field: MatchingField | None = None


class SearchResponse(BaseModel):
    """Response containing search results and metadata."""

    results: list[SearchResult]
    metadata: SearchMetadata


class ValueSchema(BaseModel):
    kind: UIType | Literal["none", "object"] = UIType.STRING
    fields: dict[str, "ValueSchema"] | None = None

    model_config = ConfigDict(extra="forbid")


class LeafInfo(BaseModel):
    name: str
    ui_types: list[UIType]
    paths: list[str]

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
    )


class ComponentInfo(BaseModel):
    name: str
    ui_types: list[UIType]

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
    )


class TypeDefinition(BaseModel):
    operators: list[FilterOp]
    valueSchema: dict[FilterOp, ValueSchema]

    model_config = ConfigDict(use_enum_values=True)
