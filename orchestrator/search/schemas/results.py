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
    value_schema: dict[FilterOp, ValueSchema]

    model_config = ConfigDict(use_enum_values=True)
