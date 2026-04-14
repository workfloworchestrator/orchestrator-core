import json
from http import HTTPStatus
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import strawberry.scalars

from orchestrator.graphql.schemas.search import (
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
from orchestrator.graphql.search_inputs import (
    FilterConditionInput,
    FilterTreeInput,
    PathFilterInput,
    SearchInput,
    StructuredOrderByInput,
)
from orchestrator.search.core.types import BooleanOperator, EntityType, FilterOp, RetrieverType, UIType
from orchestrator.search.filters.base import EqualityFilter, FilterTree, PathFilter, StringFilter
from orchestrator.search.filters.date_filters import DateRangeFilter, DateValueFilter
from orchestrator.search.filters.ltree_filters import LtreeFilter
from orchestrator.search.filters.numeric_filter import NumericRangeFilter, NumericValueFilter
from orchestrator.search.query.mixins import OrderDirection
from orchestrator.search.query.queries import SelectQuery
from test.unit_tests.config import GRAPHQL_ENDPOINT, GRAPHQL_HEADERS


@pytest.mark.parametrize(
    "op, value_kind, value, range_start, range_end, expected_type",
    [
        pytest.param(FilterOp.EQ, UIType.STRING, "active", None, None, EqualityFilter, id="eq-string"),
        pytest.param(FilterOp.NEQ, UIType.STRING, "inactive", None, None, EqualityFilter, id="neq-string"),
        pytest.param(FilterOp.LIKE, UIType.STRING, "%test%", None, None, StringFilter, id="like-string"),
        pytest.param(FilterOp.GTE, UIType.DATETIME, "2025-01-01", None, None, DateValueFilter, id="gte-datetime"),
        pytest.param(FilterOp.GTE, UIType.NUMBER, "42", None, None, NumericValueFilter, id="gte-number"),
        pytest.param(FilterOp.LT, UIType.DATETIME, "2025-01-01", None, None, DateValueFilter, id="lt-datetime"),
        pytest.param(FilterOp.LTE, UIType.DATETIME, "2025-01-01", None, None, DateValueFilter, id="lte-datetime"),
        pytest.param(FilterOp.GT, UIType.DATETIME, "2025-01-01", None, None, DateValueFilter, id="gt-datetime"),
        pytest.param(
            FilterOp.BETWEEN, UIType.DATETIME, None, "2025-01-01", "2025-12-31", DateRangeFilter, id="between-datetime"
        ),
        pytest.param(FilterOp.BETWEEN, UIType.NUMBER, None, "10", "100", NumericRangeFilter, id="between-number"),
        pytest.param(FilterOp.MATCHES_LQUERY, UIType.COMPONENT, "test", None, None, LtreeFilter, id="matches-lquery"),
        pytest.param(FilterOp.IS_ANCESTOR, UIType.COMPONENT, "test", None, None, LtreeFilter, id="is-ancestor"),
        pytest.param(FilterOp.IS_DESCENDANT, UIType.COMPONENT, "test", None, None, LtreeFilter, id="is-descendant"),
        pytest.param(FilterOp.PATH_MATCH, UIType.COMPONENT, "test", None, None, LtreeFilter, id="path-match"),
        pytest.param(FilterOp.HAS_COMPONENT, UIType.COMPONENT, "node", None, None, LtreeFilter, id="has-component"),
        pytest.param(
            FilterOp.NOT_HAS_COMPONENT, UIType.COMPONENT, "node", None, None, LtreeFilter, id="not-has-component"
        ),
        pytest.param(FilterOp.ENDS_WITH, UIType.COMPONENT, "test", None, None, LtreeFilter, id="ends-with"),
    ],
)
def test_filter_condition_dispatch(
    op: FilterOp,
    value_kind: UIType,
    value: str | None,
    range_start: str | None,
    range_end: str | None,
    expected_type: type,
) -> None:
    condition = FilterConditionInput(op=op, value=value, range_start=range_start, range_end=range_end)
    result = condition.to_pydantic(value_kind=value_kind)
    assert isinstance(result, expected_type), f"Expected {expected_type.__name__}, got {type(result).__name__}"


def test_path_filter_input_to_pydantic() -> None:
    path_input = PathFilterInput(
        path="subscription.status",
        condition=FilterConditionInput(op=FilterOp.EQ, value="active"),
        value_kind=UIType.STRING,
    )
    result = path_input.to_pydantic()
    assert isinstance(result, PathFilter)
    assert result.path == "subscription.status"
    assert result.value_kind == UIType.STRING
    assert isinstance(result.condition, EqualityFilter)


def test_filter_tree_input_flat() -> None:
    tree_input = FilterTreeInput(
        op=BooleanOperator.AND,
        filters=[
            PathFilterInput(
                path="subscription.status",
                condition=FilterConditionInput(op=FilterOp.EQ, value="active"),
                value_kind=UIType.STRING,
            ),
            PathFilterInput(
                path="subscription.product.name",
                condition=FilterConditionInput(op=FilterOp.LIKE, value="%fiber%"),
                value_kind=UIType.STRING,
            ),
        ],
    )
    result = tree_input.to_pydantic()
    assert isinstance(result, FilterTree)
    assert result.op == BooleanOperator.AND
    assert len(result.children) == 2
    assert all(isinstance(c, PathFilter) for c in result.children)


def test_filter_tree_input_nested() -> None:
    tree_input = FilterTreeInput(
        op=BooleanOperator.AND,
        filters=[
            PathFilterInput(
                path="subscription.start_date",
                condition=FilterConditionInput(op=FilterOp.GTE, value="2024-01-01"),
                value_kind=UIType.DATETIME,
            ),
        ],
        groups=[
            FilterTreeInput(
                op=BooleanOperator.OR,
                filters=[
                    PathFilterInput(
                        path="subscription.product.name",
                        condition=FilterConditionInput(op=FilterOp.LIKE, value="%fiber%"),
                        value_kind=UIType.STRING,
                    ),
                    PathFilterInput(
                        path="subscription.customer_id",
                        condition=FilterConditionInput(op=FilterOp.EQ, value="Surf"),
                        value_kind=UIType.STRING,
                    ),
                ],
            ),
        ],
    )
    result = tree_input.to_pydantic()
    assert isinstance(result, FilterTree)
    assert result.op == BooleanOperator.AND
    assert len(result.children) == 2

    assert isinstance(result.children[0], PathFilter)

    nested = result.children[1]
    assert isinstance(nested, FilterTree)
    assert nested.op == BooleanOperator.OR
    assert len(nested.children) == 2


def test_search_input_to_select_query() -> None:
    search = SearchInput(
        query="fiber",
        filters=FilterTreeInput(
            op=BooleanOperator.AND,
            filters=[
                PathFilterInput(
                    path="subscription.status",
                    condition=FilterConditionInput(op=FilterOp.EQ, value="active"),
                    value_kind=UIType.STRING,
                ),
            ],
        ),
        limit=5,
        retriever=RetrieverType.FUZZY,
        response_columns=["subscription.status", "subscription.product.name"],
    )
    result = search.to_select_query(EntityType.SUBSCRIPTION)
    assert isinstance(result, SelectQuery)
    assert result.entity_type == EntityType.SUBSCRIPTION
    assert result.query_text == "fiber"
    assert result.limit == 5
    assert result.retriever == RetrieverType.FUZZY
    assert result.filters is not None
    assert result.response_columns == ["subscription.status", "subscription.product.name"]


def test_search_input_minimal() -> None:
    search = SearchInput()
    result = search.to_select_query(EntityType.PRODUCT)
    assert isinstance(result, SelectQuery)
    assert result.entity_type == EntityType.PRODUCT
    assert result.query_text is None
    assert result.filters is None
    assert result.limit == 10
    assert result.retriever is None
    assert result.order_by is None
    assert result.response_columns is None


def test_search_input_with_order_by() -> None:
    search = SearchInput(
        order_by=StructuredOrderByInput(element="subscription.start_date", direction=OrderDirection.DESC),
    )
    result = search.to_select_query(EntityType.SUBSCRIPTION)
    assert result.order_by is not None
    assert result.order_by.element == "subscription.start_date"
    assert result.order_by.direction == OrderDirection.DESC


def test_comparison_op_invalid_value_kind_raises() -> None:
    condition = FilterConditionInput(op=FilterOp.GT, value="42")
    with pytest.raises(ValueError, match="Operator .* is not valid for value_kind"):
        condition.to_pydantic(value_kind=UIType.STRING)


def test_empty_filter_tree_raises() -> None:
    tree_input = FilterTreeInput(op=BooleanOperator.AND)
    with pytest.raises(ValueError, match="FilterTreeInput must contain at least one filter or group"):
        tree_input.to_pydantic()


# === Output type tests ===


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
        matching_field=MatchingFieldType(text="fiber", path="product.name"),
        response_columns=strawberry.scalars.JSON({"status": "active"}),
    )
    assert result.entity_id == "abc-123"
    assert result.entity_type == EntityType.SUBSCRIPTION
    assert result.entity_title == "Fiber Subscription"
    assert result.score == 0.95
    assert result.perfect_match == 1
    assert result.matching_field is not None
    assert result.matching_field.text == "fiber"
    assert result.response_columns == strawberry.scalars.JSON({"status": "active"})


def test_search_result_type_defaults() -> None:
    result = SearchResultType(
        entity_id="x",
        entity_type=EntityType.PRODUCT,
        entity_title="Product",
        score=0.5,
    )
    assert result.perfect_match == 0
    assert result.matching_field is None
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


# === GraphQL integration tests ===

SEARCH_QUERY = """
query SearchQuery($entityType: EntityType!, $input: SearchInput!) {
    search(entityType: $entityType, input: $input) {
        data {
            entityId
            entityType
            entityTitle
            score
            perfectMatch
            matchingField {
                text
                path
                highlightIndices
            }
            responseColumns
        }
        pageInfo {
            hasNextPage
            nextPageCursor
        }
        searchMetadata {
            searchType
            description
        }
        cursor {
            totalItems
            startCursor
            endCursor
        }
    }
}
"""

SEARCH_PATHS_QUERY = """
query SearchPathsQuery($prefix: String, $q: String, $entityType: EntityType, $limit: Int) {
    searchPaths(prefix: $prefix, q: $q, entityType: $entityType, limit: $limit) {
        leaves {
            name
            uiTypes
            paths
        }
        components {
            name
            uiTypes
        }
    }
}
"""

SEARCH_DEFINITIONS_QUERY = """
query SearchDefinitionsQuery {
    searchDefinitions {
        uiType
        operators
        valueSchema {
            operator
            kind
            fields {
                operator
                kind
            }
        }
    }
}
"""

SEARCH_QUERY_BY_ID = """
query SearchQueryById($queryId: String!, $cursor: String) {
    searchQuery(queryId: $queryId, cursor: $cursor) {
        data {
            entityId
            entityType
            entityTitle
            score
        }
        pageInfo {
            hasNextPage
            nextPageCursor
        }
        searchMetadata {
            searchType
            description
        }
    }
}
"""

SEARCH_QUERY_RESULTS = """
query SearchQueryResults($queryId: String!) {
    searchQueryResults(queryId: $queryId) {
        results {
            groupValues {
                key
                value
            }
            aggregations {
                key
                value
            }
        }
        totalResults
        metadata {
            searchType
            description
        }
        visualizationType {
            type
        }
    }
}
"""

SEARCH_QUERY_EXPORT = """
query SearchQueryExport($queryId: String!) {
    searchQueryExport(queryId: $queryId) {
        page
    }
}
"""


def test_search_definitions_query(test_client_graphql) -> None:
    data = json.dumps({"query": SEARCH_DEFINITIONS_QUERY})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    definitions = result["data"]["searchDefinitions"]
    assert isinstance(definitions, list)
    assert len(definitions) > 0
    for defn in definitions:
        assert "uiType" in defn
        assert "operators" in defn
        assert isinstance(defn["operators"], list)
        assert "valueSchema" in defn


@pytest.mark.search
def test_search_paths_query(test_client_graphql) -> None:
    data = json.dumps({"query": SEARCH_PATHS_QUERY, "variables": {"entityType": "SUBSCRIPTION", "limit": 5}})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    paths_data = result["data"]["searchPaths"]
    assert "leaves" in paths_data
    assert "components" in paths_data
    assert isinstance(paths_data["leaves"], list)
    assert isinstance(paths_data["components"], list)


@pytest.mark.search
def test_search_subscriptions(test_client_graphql) -> None:
    data = json.dumps(
        {
            "query": SEARCH_QUERY,
            "variables": {"entityType": "SUBSCRIPTION", "input": {"limit": 5}},
        }
    )
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    search_data = result["data"]["search"]
    assert "data" in search_data
    assert "pageInfo" in search_data
    assert isinstance(search_data["data"], list)


@pytest.mark.search
def test_search_with_filters(test_client_graphql) -> None:
    data = json.dumps(
        {
            "query": SEARCH_QUERY,
            "variables": {
                "entityType": "SUBSCRIPTION",
                "input": {
                    "limit": 5,
                    "filters": {
                        "op": "AND",
                        "filters": [
                            {
                                "path": "subscription.status",
                                "condition": {"op": "EQ", "value": "active"},
                                "valueKind": "STRING",
                            }
                        ],
                    },
                },
            },
        }
    )
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    search_data = result["data"]["search"]
    assert isinstance(search_data["data"], list)


@pytest.mark.search
def test_search_with_text_query(test_client_graphql) -> None:
    fake_embedding = [0.0] * 1536
    data = json.dumps(
        {
            "query": SEARCH_QUERY,
            "variables": {
                "entityType": "SUBSCRIPTION",
                "input": {"query": "fiber", "limit": 5},
            },
        }
    )
    with patch(
        "orchestrator.search.core.embedding.QueryEmbedder.generate_for_text_async",
        new=AsyncMock(return_value=fake_embedding),
    ):
        response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    search_data = result["data"]["search"]
    assert isinstance(search_data["data"], list)


@pytest.mark.search
@pytest.mark.parametrize("entity_type", ["SUBSCRIPTION", "PRODUCT", "WORKFLOW", "PROCESS"])
def test_search_all_entity_types(test_client_graphql, entity_type: str) -> None:
    data = json.dumps(
        {
            "query": SEARCH_QUERY,
            "variables": {"entityType": entity_type, "input": {"limit": 3}},
        }
    )
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    search_data = result["data"]["search"]
    assert isinstance(search_data["data"], list)
    assert "pageInfo" in search_data


def test_search_query_not_found(test_client_graphql) -> None:
    query_id = str(uuid4())
    data = json.dumps({"query": SEARCH_QUERY_BY_ID, "variables": {"queryId": query_id}})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" in result
    assert len(result["errors"]) > 0


def test_search_query_results_not_found(test_client_graphql) -> None:
    query_id = str(uuid4())
    data = json.dumps({"query": SEARCH_QUERY_RESULTS, "variables": {"queryId": query_id}})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" in result
    assert len(result["errors"]) > 0


def test_search_query_export_not_found(test_client_graphql) -> None:
    query_id = str(uuid4())
    data = json.dumps({"query": SEARCH_QUERY_EXPORT, "variables": {"queryId": query_id}})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" in result
    assert len(result["errors"]) > 0


@pytest.mark.search
def test_search_invalid_limit(test_client_graphql) -> None:
    data = json.dumps(
        {
            "query": SEARCH_PATHS_QUERY,
            "variables": {"entityType": "SUBSCRIPTION", "limit": 100},
        }
    )
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    paths_data = result["data"]["searchPaths"]
    assert isinstance(paths_data["leaves"], list)
    assert isinstance(paths_data["components"], list)
