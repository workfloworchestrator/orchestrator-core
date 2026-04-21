# Copyright 2019-2026 SURF.
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
from __future__ import annotations  # required: ValueSchemaType references itself

from enum import Enum

import strawberry
import strawberry.scalars

from orchestrator.core.search.core.types import EntityType, FilterOp, UIType


@strawberry.type
class MatchingFieldType:
    text: str
    path: str
    highlight_indices: list[tuple[int, int]] | None = None


@strawberry.type
class SearchResultType:
    entity_id: str
    entity_type: EntityType
    entity_title: str
    score: float
    perfect_match: int = 0
    matching_field: MatchingFieldType | None = None
    response_columns: strawberry.scalars.JSON | None = None


@strawberry.type
class SearchMetadataType:
    search_type: str
    description: str


@strawberry.type
class SearchPageInfoType:
    has_next_page: bool = False
    next_page_cursor: str | None = None


@strawberry.type
class CursorInfoType:
    total_items: int | None = None
    start_cursor: int | None = None
    end_cursor: int | None = None


@strawberry.type
class SearchResultsConnection:
    data: list[SearchResultType]
    page_info: SearchPageInfoType
    search_metadata: SearchMetadataType | None = None
    cursor: CursorInfoType | None = None


@strawberry.type
class LeafInfoType:
    name: str
    ui_types: list[UIType]
    paths: list[str]


@strawberry.type
class ComponentInfoType:
    name: str
    ui_types: list[UIType]


@strawberry.type
class PathsResponseType:
    leaves: list[LeafInfoType]
    components: list[ComponentInfoType]


@strawberry.enum(description="Visualization render type for aggregation results")
class VisualizationKind(str, Enum):
    PIE = "pie"
    LINE = "line"
    TABLE = "table"


@strawberry.type(description="Visualization type for aggregation results")
class VisualizationType:
    type: VisualizationKind = VisualizationKind.TABLE


@strawberry.type(description="A key-value pair for group values")
class GroupValuePairType:
    key: str
    value: str


@strawberry.type(description="A key-value pair for aggregation values")
class AggregationPairType:
    key: str
    value: float


@strawberry.type(description="A single result row with group values and aggregation values")
class ResultRowType:
    group_values: list[GroupValuePairType]
    aggregations: list[AggregationPairType]


@strawberry.type
class QueryResultsResponseType:
    results: list[ResultRowType]
    total_results: int
    metadata: SearchMetadataType
    visualization_type: VisualizationType


@strawberry.type
class ExportResponseType:
    page: list[strawberry.scalars.JSON]


@strawberry.type
class ValueSchemaType:
    operator: FilterOp
    kind: str
    fields: list[ValueSchemaType] | None = None


@strawberry.type
class TypeDefinitionType:
    ui_type: UIType
    operators: list[FilterOp]
    value_schema: list[ValueSchemaType]
