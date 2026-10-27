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

"""Unit tests for the GraphQL search output types in orchestrator.core.graphql.schemas.search."""

import strawberry.scalars

from orchestrator.core.graphql.schemas.search import (
    AggregationPairType,
    ComponentInfoType,
    CursorInfoType,
    ExportResponseType,
    GroupValuePairType,
    LeafInfoType,
    MatchingFieldType,
    PathsResponseType,
    QueryResultsResponseType,
    ResultRowType,
    SearchMetadataType,
    SearchPageInfoType,
    SearchResultsConnection,
    SearchResultType,
    TypeDefinitionType,
    ValueSchemaType,
    VisualizationKind,
    VisualizationType,
)
from orchestrator.core.search.core.types import EntityType, FilterOp, UIType


def test_matching_field_type() -> None:
    field = MatchingFieldType(text="fiber optic", path="subscription.description", highlight_indices=[(0, 5)])
    assert field.text == "fiber optic"
    assert field.path == "subscription.description"
    assert field.highlight_indices == [(0, 5)]


def test_matching_field_type_no_highlights() -> None:
    field = MatchingFieldType(text="test", path="name")
    assert field.highlight_indices is None


def test_search_result_type() -> None:
    result = SearchResultType(
        entity_id="abc-123",
        entity_type=EntityType.SUBSCRIPTION,
        entity_title="Fiber Subscription",
        score=0.95,
        perfect_match=1,
        matching_fields=[MatchingFieldType(text="fiber", path="product.name")],
        response_columns=strawberry.scalars.JSON({"status": "active"}),
    )
    assert result.entity_id == "abc-123"
    assert result.entity_type == EntityType.SUBSCRIPTION
    assert result.entity_title == "Fiber Subscription"
    assert result.score == 0.95
    assert result.perfect_match == 1
    assert len(result.matching_fields) == 1
    assert result.matching_fields[0].text == "fiber"
    assert result.response_columns == strawberry.scalars.JSON({"status": "active"})


def test_search_result_type_defaults() -> None:
    result = SearchResultType(
        entity_id="x",
        entity_type=EntityType.PRODUCT,
        entity_title="Product",
        score=0.5,
    )
    assert result.perfect_match == 0
    assert result.matching_fields == []
    assert result.response_columns is None


def test_search_metadata_type() -> None:
    metadata = SearchMetadataType(search_type="fuzzy", description="Trigram similarity search")
    assert metadata.search_type == "fuzzy"
    assert metadata.description == "Trigram similarity search"


def test_search_results_connection() -> None:
    connection = SearchResultsConnection(
        data=[
            SearchResultType(
                entity_id="id-1",
                entity_type=EntityType.SUBSCRIPTION,
                entity_title="Sub 1",
                score=0.9,
            ),
            SearchResultType(
                entity_id="id-2",
                entity_type=EntityType.PRODUCT,
                entity_title="Prod 1",
                score=0.8,
            ),
        ],
        page_info=SearchPageInfoType(has_next_page=True, next_page_cursor="cursor-abc"),
        search_metadata=SearchMetadataType(search_type="structured", description="Structured query"),
        cursor=CursorInfoType(total_items=100, start_cursor=0, end_cursor=10),
    )
    assert len(connection.data) == 2
    assert connection.page_info.has_next_page is True
    assert connection.page_info.next_page_cursor == "cursor-abc"
    assert connection.search_metadata is not None
    assert connection.search_metadata.search_type == "structured"
    assert connection.cursor is not None
    assert connection.cursor.total_items == 100
    assert connection.cursor.start_cursor == 0
    assert connection.cursor.end_cursor == 10


def test_search_results_connection_minimal() -> None:
    connection = SearchResultsConnection(
        data=[],
        page_info=SearchPageInfoType(),
    )
    assert connection.data == []
    assert connection.page_info.has_next_page is False
    assert connection.page_info.next_page_cursor is None
    assert connection.search_metadata is None
    assert connection.cursor is None


def test_paths_response_type() -> None:
    response = PathsResponseType(
        leaves=[
            LeafInfoType(name="status", ui_types=[UIType.STRING], paths=["subscription.status"]),
            LeafInfoType(
                name="start_date", ui_types=[UIType.DATETIME], paths=["subscription.start_date", "process.start_date"]
            ),
        ],
        components=[
            ComponentInfoType(name="subscription", ui_types=[UIType.COMPONENT]),
        ],
    )
    assert len(response.leaves) == 2
    assert response.leaves[0].name == "status"
    assert response.leaves[0].ui_types == [UIType.STRING]
    assert response.leaves[0].paths == ["subscription.status"]
    assert len(response.leaves[1].paths) == 2
    assert len(response.components) == 1
    assert response.components[0].name == "subscription"


def test_query_results_response_type() -> None:
    response = QueryResultsResponseType(
        results=[
            ResultRowType(
                group_values=[
                    GroupValuePairType(key="product", value="Fiber"),
                    GroupValuePairType(key="status", value="active"),
                ],
                aggregations=[
                    AggregationPairType(key="count", value=42.0),
                    AggregationPairType(key="avg_speed", value=100.5),
                ],
            ),
            ResultRowType(
                group_values=[
                    GroupValuePairType(key="product", value="Wireless"),
                    GroupValuePairType(key="status", value="active"),
                ],
                aggregations=[
                    AggregationPairType(key="count", value=10.0),
                    AggregationPairType(key="avg_speed", value=50.0),
                ],
            ),
        ],
        total_results=2,
        metadata=SearchMetadataType(search_type="structured", description="Aggregation query"),
        visualization_type=VisualizationType(type=VisualizationKind.PIE),
    )
    assert len(response.results) == 2
    assert response.results[0].group_values[0].key == "product"
    assert response.results[0].group_values[0].value == "Fiber"
    assert response.results[0].aggregations[0].key == "count"
    assert response.results[0].aggregations[0].value == 42.0
    assert response.total_results == 2
    assert response.metadata.search_type == "structured"
    assert response.visualization_type.type == VisualizationKind.PIE


def test_query_results_response_type_default_visualization() -> None:
    response = QueryResultsResponseType(
        results=[],
        total_results=0,
        metadata=SearchMetadataType(search_type="structured", description="Empty"),
        visualization_type=VisualizationType(),
    )
    assert response.visualization_type.type == VisualizationKind.TABLE


def test_export_response_type() -> None:
    er = ExportResponseType(page=[strawberry.scalars.JSON({"id": "123", "name": "test"})])
    assert len(er.page) == 1


def test_type_definition_type() -> None:
    definition = TypeDefinitionType(
        ui_type=UIType.STRING,
        operators=[FilterOp.EQ, FilterOp.NEQ, FilterOp.LIKE],
        value_schema=[
            ValueSchemaType(operator=FilterOp.EQ, kind="single"),
            ValueSchemaType(operator=FilterOp.LIKE, kind="single"),
            ValueSchemaType(
                operator=FilterOp.BETWEEN,
                kind="range",
                fields=[
                    ValueSchemaType(operator=FilterOp.GTE, kind="start"),
                    ValueSchemaType(operator=FilterOp.LTE, kind="end"),
                ],
            ),
        ],
    )
    assert definition.ui_type == UIType.STRING
    assert len(definition.operators) == 3
    assert FilterOp.LIKE in definition.operators
    assert len(definition.value_schema) == 3
    assert definition.value_schema[2].fields is not None
    assert len(definition.value_schema[2].fields) == 2
    assert definition.value_schema[2].fields[0].kind == "start"


def test_value_schema_type_no_fields() -> None:
    schema = ValueSchemaType(operator=FilterOp.EQ, kind="single")
    assert schema.operator == FilterOp.EQ
    assert schema.kind == "single"
    assert schema.fields is None
