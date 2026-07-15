# Search GraphQL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose all search REST API endpoints (`/api/search/*`) through the GraphQL schema using Strawberry, reusing the existing search service layer.

**Architecture:** Create new Strawberry input/output types mirroring the Pydantic search models, add a unified `search` query field with `entity_type` as a parameter (instead of separate per-entity endpoints), plus dedicated query fields for `searchPaths`, `searchDefinitions`, `searchQueryResults`, `searchQuery`, and `searchQueryExport`. All resolvers delegate directly to the existing `engine.execute_search()`, `engine.execute_export()`, `engine.execute_aggregation()`, and builder functions.

**Tech Stack:** Strawberry GraphQL, Pydantic v2, SQLAlchemy, existing search engine/retriever layer

---

## File Structure

```
orchestrator/graphql/
  schemas/search.py          — (Create) Strawberry output types: SearchResultType, MatchingFieldType, SearchResultsConnection, SearchMetadataType, CursorInfoType, PathsResponseType, LeafInfoType, ComponentInfoType, QueryResultsResponseType, ResultRowType, VisualizationTypeGql, ExportResponseType, TypeDefinitionType, ValueSchemaType
  types/search_inputs.py     — (Create) Strawberry input types: SearchInput, FilterTreeInput, PathFilterInput, FilterConditionInput, StructuredOrderByInput, SearchPathsInput, SearchQueryInput
  resolvers/search.py        — (Create) Resolver functions: resolve_search, resolve_search_paths, resolve_search_definitions, resolve_search_query_results, resolve_search_query, resolve_search_query_export
  resolvers/__init__.py      — (Modify) Export new resolvers
  schema.py                  — (Modify) Add SearchQuery type, merge into Query
  __init__.py                — (Modify) Export SearchQuery
test/unit_tests/graphql/
  test_search.py             — (Create) Tests for all search GraphQL resolvers
```

---

### Task 1: Strawberry Search Input Types

**Files:**
- Create: `orchestrator/graphql/types/search_inputs.py`

These input types mirror the Pydantic models in `orchestrator/search/filters/base.py`, `orchestrator/search/core/types.py`, `orchestrator/schemas/search_requests.py`, and `orchestrator/search/query/mixins.py`. The core challenge is representing the `FilterCondition` union (DateFilter | NumericFilter | StringFilter | LtreeFilter | EqualityFilter) in GraphQL — since GraphQL doesn't support union input types, we use a flat input with optional fields and convert to the appropriate Pydantic model in the resolver.

- [ ] **Step 1: Write failing test for input type conversion**

Create the test file first:

```python
# test/unit_tests/graphql/test_search.py
import pytest

from orchestrator.graphql.search_inputs import FilterConditionInput, FilterTreeInput, PathFilterInput, SearchInput
from orchestrator.search.core.types import BooleanOperator, EntityType, FilterOp, RetrieverType, UIType
from orchestrator.search.filters.base import EqualityFilter, FilterTree, PathFilter, StringFilter
from orchestrator.search.filters.date_filters import DateValueFilter
from orchestrator.search.filters.ltree_filters import LtreeFilter
from orchestrator.search.filters.numeric_filter import NumericRangeFilter
from orchestrator.search.query.queries import SelectQuery


def test_equality_filter_condition_to_pydantic():
    gql_input = FilterConditionInput(op=FilterOp.EQ, value="active")
    pydantic_model = gql_input.to_pydantic(UIType.STRING)

    assert isinstance(pydantic_model, EqualityFilter)
    assert pydantic_model.op == FilterOp.EQ
    assert pydantic_model.value == "active"


def test_like_filter_condition_to_pydantic():
    gql_input = FilterConditionInput(op=FilterOp.LIKE, value="%fiber%")
    pydantic_model = gql_input.to_pydantic(UIType.STRING)

    assert isinstance(pydantic_model, StringFilter)
    assert pydantic_model.value == "%fiber%"


def test_numeric_between_filter_condition_to_pydantic():
    gql_input = FilterConditionInput(op=FilterOp.BETWEEN, value=None, range_start="10", range_end="20")
    pydantic_model = gql_input.to_pydantic(UIType.NUMBER)

    assert isinstance(pydantic_model, NumericRangeFilter)


def test_date_gte_filter_condition_to_pydantic():
    gql_input = FilterConditionInput(op=FilterOp.GTE, value="2025-01-01")
    pydantic_model = gql_input.to_pydantic(UIType.DATETIME)

    assert isinstance(pydantic_model, DateValueFilter)
    assert pydantic_model.op == FilterOp.GTE


def test_ltree_has_component_filter_condition_to_pydantic():
    gql_input = FilterConditionInput(op=FilterOp.HAS_COMPONENT, value="node")
    pydantic_model = gql_input.to_pydantic(UIType.COMPONENT)

    assert isinstance(pydantic_model, LtreeFilter)
    assert pydantic_model.op == FilterOp.HAS_COMPONENT


@pytest.mark.parametrize(
    "op,value,value_kind,expected_type_name",
    [
        pytest.param(FilterOp.EQ, "active", UIType.STRING, "EqualityFilter", id="eq-string"),
        pytest.param(FilterOp.NEQ, "false", UIType.BOOLEAN, "EqualityFilter", id="neq-boolean"),
        pytest.param(FilterOp.LIKE, "%test%", UIType.STRING, "StringFilter", id="like-string"),
        pytest.param(FilterOp.GT, "100", UIType.NUMBER, "NumericValueFilter", id="gt-number"),
        pytest.param(FilterOp.LT, "2025-01-01", UIType.DATETIME, "DateValueFilter", id="lt-datetime"),
        pytest.param(FilterOp.ENDS_WITH, "status", UIType.COMPONENT, "LtreeFilter", id="ends-with-component"),
    ],
)
def test_filter_condition_dispatch(op, value, value_kind, expected_type_name):
    gql_input = FilterConditionInput(op=op, value=value)
    pydantic_model = gql_input.to_pydantic(value_kind)
    assert type(pydantic_model).__name__ == expected_type_name


def test_path_filter_input_to_pydantic():
    gql_input = PathFilterInput(
        path="subscription.status",
        condition=FilterConditionInput(op=FilterOp.EQ, value="active"),
        value_kind=UIType.STRING,
    )
    pydantic_model = gql_input.to_pydantic()

    assert isinstance(pydantic_model, PathFilter)
    assert pydantic_model.path == "subscription.status"


def test_filter_tree_input_to_pydantic():
    gql_input = FilterTreeInput(
        op=BooleanOperator.AND,
        filters=[
            PathFilterInput(
                path="subscription.status",
                condition=FilterConditionInput(op=FilterOp.EQ, value="active"),
                value_kind=UIType.STRING,
            ),
        ],
        groups=[],
    )
    pydantic_model = gql_input.to_pydantic()

    assert isinstance(pydantic_model, FilterTree)
    assert pydantic_model.op == BooleanOperator.AND
    assert len(pydantic_model.children) == 1


def test_nested_filter_tree_input_to_pydantic():
    gql_input = FilterTreeInput(
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
                groups=[],
            ),
        ],
    )
    pydantic_model = gql_input.to_pydantic()

    assert pydantic_model.op == BooleanOperator.AND
    assert len(pydantic_model.children) == 2  # 1 filter + 1 nested group


def test_search_input_to_select_query():
    gql_input = SearchInput(
        query="fiber activation",
        limit=20,
        retriever=RetrieverType.HYBRID,
    )
    select_query = gql_input.to_select_query(EntityType.SUBSCRIPTION)

    assert isinstance(select_query, SelectQuery)
    assert select_query.entity_type == EntityType.SUBSCRIPTION
    assert select_query.query_text == "fiber activation"
    assert select_query.limit == 20
    assert select_query.retriever == RetrieverType.HYBRID
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest test/unit_tests/graphql/test_search.py::test_equality_filter_condition_to_pydantic -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'orchestrator.graphql.search_inputs'`

- [ ] **Step 3: Create the types directory and input types module**

First ensure the types directory is a package. Check if `orchestrator/graphql/types/__init__.py` exists — if not, note that `types.py` is currently a module file, not a package. We'll create a new file `orchestrator/graphql/types/search_inputs.py` alongside the existing `orchestrator/graphql/types.py` which is not a package directory. Since `types.py` is a file (not a directory), we'll place our new module at `orchestrator/graphql/search_inputs.py` instead.

**Updated file:** `orchestrator/graphql/search_inputs.py`

```python
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

"""Strawberry GraphQL input types for the search subsystem."""

from __future__ import annotations

import strawberry

from orchestrator.search.core.types import BooleanOperator, EntityType, FilterOp, RetrieverType, UIType
from orchestrator.search.filters.base import (
    EqualityFilter,
    FilterTree,
    PathFilter,
    StringFilter,
)
from orchestrator.search.filters.date_filters import DateFilter, DateRangeFilter, DateValueFilter
from orchestrator.search.filters.ltree_filters import LtreeFilter
from orchestrator.search.filters.numeric_filter import NumericFilter, NumericRangeFilter, NumericValueFilter
from orchestrator.search.query.mixins import OrderDirection, StructuredOrderBy, StructuredOrderByElement
from orchestrator.search.query.queries import SelectQuery

# --- Enums registered with Strawberry ---

StrawberryFilterOp = strawberry.enum(FilterOp, name="FilterOp", description="Filter operators for search conditions")
StrawberryBooleanOperator = strawberry.enum(
    BooleanOperator, name="BooleanOperator", description="Boolean operators for combining filters"
)
StrawberryEntityType = strawberry.enum(EntityType, name="SearchEntityType", description="Entity types for search")
StrawberryRetrieverType = strawberry.enum(
    RetrieverType, name="RetrieverType", description="Retriever types for search"
)
StrawberryUIType = strawberry.enum(UIType, name="UIType", description="UI types for filter value kinds")
StrawberryOrderDirection = strawberry.enum(
    OrderDirection, name="SearchOrderDirection", description="Sort direction for structured ordering"
)


# --- Ltree/Numeric/Date ops that are path-only ---
_LTREE_OPS = frozenset({FilterOp.MATCHES_LQUERY, FilterOp.IS_ANCESTOR, FilterOp.IS_DESCENDANT, FilterOp.PATH_MATCH, FilterOp.HAS_COMPONENT, FilterOp.NOT_HAS_COMPONENT, FilterOp.ENDS_WITH})
_COMPARISON_OPS = frozenset({FilterOp.LT, FilterOp.LTE, FilterOp.GT, FilterOp.GTE})


def _build_filter_condition(op: FilterOp, value: str | None, value_kind: UIType, range_start: str | None, range_end: str | None) -> DateFilter | NumericFilter | StringFilter | LtreeFilter | EqualityFilter:
    """Convert flat GraphQL input fields into the correct Pydantic filter condition."""
    if op in _LTREE_OPS:
        return LtreeFilter(op=op, value=value or "")

    if op == FilterOp.LIKE:
        return StringFilter(op=op, value=value or "")

    if op == FilterOp.BETWEEN:
        if value_kind == UIType.DATETIME:
            return DateRangeFilter(op=op, value={"start": range_start or "", "end": range_end or ""})
        return NumericRangeFilter(op=op, value={"start": range_start or "", "end": range_end or ""})

    if op in _COMPARISON_OPS:
        if value_kind == UIType.DATETIME:
            return DateValueFilter(op=op, value=value or "")
        if value_kind == UIType.NUMBER:
            return NumericValueFilter(op=op, value=value or "")

    # Default: equality filter (EQ, NEQ for string/boolean/uuid)
    return EqualityFilter(op=op, value=value)


@strawberry.input(description="Filter condition specifying operator and value(s)")
class FilterConditionInput:
    op: FilterOp
    value: str | None = None
    range_start: str | None = strawberry.field(default=None, description="Start value for BETWEEN operator")
    range_end: str | None = strawberry.field(default=None, description="End value for BETWEEN operator")

    def to_pydantic(self, value_kind: UIType) -> DateFilter | NumericFilter | StringFilter | LtreeFilter | EqualityFilter:
        return _build_filter_condition(self.op, self.value, value_kind, self.range_start, self.range_end)


@strawberry.input(description="A leaf filter on a specific field path")
class PathFilterInput:
    path: str = strawberry.field(description="The ltree path of the field, e.g. 'subscription.status'")
    condition: FilterConditionInput
    value_kind: UIType = strawberry.field(description="The UI type of the value being filtered")

    def to_pydantic(self) -> PathFilter:
        condition = self.condition.to_pydantic(self.value_kind)
        return PathFilter(path=self.path, condition=condition, value_kind=self.value_kind)


@strawberry.input(description="Boolean filter tree combining path filters with AND/OR")
class FilterTreeInput:
    op: BooleanOperator = strawberry.field(default=BooleanOperator.AND, description="Boolean operator (AND/OR)")
    filters: list[PathFilterInput] = strawberry.field(default_factory=list, description="Leaf path filters")
    groups: list[FilterTreeInput] = strawberry.field(default_factory=list, description="Nested filter groups")

    def to_pydantic(self) -> FilterTree:
        children: list[FilterTree | PathFilter] = [f.to_pydantic() for f in self.filters]
        children.extend(g.to_pydantic() for g in self.groups)
        return FilterTree(op=self.op, children=children)


@strawberry.input(description="Ordering element for structured search results")
class StructuredOrderByElementInput:
    field: str
    direction: OrderDirection = OrderDirection.ASC

    def to_pydantic(self) -> StructuredOrderByElement:
        return StructuredOrderByElement(field=self.field, direction=self.direction)


@strawberry.input(description="Ordering instructions for structured (filter-only) search")
class StructuredOrderByInput:
    elements: list[StructuredOrderByElementInput]

    def to_pydantic(self) -> StructuredOrderBy:
        return StructuredOrderBy(elements=[e.to_pydantic() for e in self.elements])


@strawberry.input(description="Search request input")
class SearchInput:
    query: str | None = strawberry.field(default=None, description="Text search query for semantic/fuzzy search")
    filters: FilterTreeInput | None = strawberry.field(default=None, description="Structured filter tree")
    limit: int = strawberry.field(default=10, description="Maximum results to return (1-30)")
    retriever: RetrieverType | None = strawberry.field(default=None, description="Force a specific retriever type")
    order_by: StructuredOrderByInput | None = strawberry.field(
        default=None, description="Ordering for structured search (only when query is empty)"
    )
    response_columns: list[str] | None = strawberry.field(
        default=None, description="Field paths to return as inline columns"
    )

    def to_select_query(self, entity_type: EntityType) -> SelectQuery:
        return SelectQuery(
            entity_type=entity_type,
            filters=self.filters.to_pydantic() if self.filters else None,
            query_text=self.query,
            limit=self.limit,
            retriever=self.retriever,
            order_by=self.order_by.to_pydantic() if self.order_by else None,
            response_columns=self.response_columns,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest test/unit_tests/graphql/test_search.py -k "filter_condition or path_filter or filter_tree or search_input" -v`
Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/graphql/search_inputs.py test/unit_tests/graphql/test_search.py
git commit -m "feat(graphql): add Strawberry search input types with filter tree conversion"
```

---

### Task 2: Strawberry Search Output Types

**Files:**
- Create: `orchestrator/graphql/schemas/search.py`

These types map the Pydantic response models from `orchestrator/schemas/search.py`, `orchestrator/search/query/results.py`, and `orchestrator/search/filters/definitions.py` to Strawberry GraphQL types.

- [ ] **Step 1: Write failing test for output type creation**

Append to `test/unit_tests/graphql/test_search.py`:

```python
from orchestrator.graphql.schemas.search import (
    ComponentInfoType,
    CursorInfoType,
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
    VisualizationTypeGql,
)


def test_matching_field_type():
    mf = MatchingFieldType(text="fiber activation", path="subscription.description", highlight_indices=[(0, 5)])
    assert mf.text == "fiber activation"
    assert mf.path == "subscription.description"
    assert mf.highlight_indices == [(0, 5)]


def test_search_result_type():
    sr = SearchResultType(
        entity_id="uuid-123",
        entity_type=EntityType.SUBSCRIPTION,
        entity_title="Test Sub",
        score=0.95,
        perfect_match=1,
        matching_field=None,
        response_columns=None,
    )
    assert sr.entity_id == "uuid-123"
    assert sr.score == 0.95


def test_search_metadata_type():
    sm = SearchMetadataType(search_type="hybrid", description="test description")
    assert sm.search_type == "hybrid"


def test_search_results_connection():
    conn = SearchResultsConnection(
        data=[
            SearchResultType(
                entity_id="id1",
                entity_type=EntityType.SUBSCRIPTION,
                entity_title="Sub 1",
                score=0.9,
                perfect_match=0,
                matching_field=None,
                response_columns=None,
            )
        ],
        page_info=SearchPageInfoType(has_next_page=True, next_page_cursor="abc123"),
        search_metadata=SearchMetadataType(search_type="fuzzy", description="test"),
        cursor=CursorInfoType(total_items=100, start_cursor=0, end_cursor=9),
    )
    assert len(conn.data) == 1
    assert conn.page_info.has_next_page is True


def test_paths_response_type():
    pr = PathsResponseType(
        leaves=[LeafInfoType(name="status", ui_types=[UIType.STRING], paths=["subscription.status"])],
        components=[ComponentInfoType(name="product", ui_types=[UIType.COMPONENT])],
    )
    assert len(pr.leaves) == 1
    assert pr.components[0].name == "product"


def test_query_results_response_type():
    qr = QueryResultsResponseType(
        results=[ResultRowType(group_values=[("status", "active")], aggregations=[("count", 42)])],
        total_results=1,
        metadata=SearchMetadataType(search_type="aggregation", description="test"),
        visualization_type=VisualizationTypeGql(type="pie"),
    )
    assert qr.total_results == 1


def test_type_definition_type():
    td = TypeDefinitionType(
        ui_type=UIType.STRING,
        operators=[FilterOp.EQ, FilterOp.NEQ, FilterOp.LIKE],
        value_schema=[
            ValueSchemaType(operator=FilterOp.EQ, kind="string", fields=None),
        ],
    )
    assert len(td.operators) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest test/unit_tests/graphql/test_search.py::test_matching_field_type -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'orchestrator.graphql.schemas.search'`

- [ ] **Step 3: Create output types module**

```python
# orchestrator/graphql/schemas/search.py
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

"""Strawberry GraphQL output types for the search subsystem."""

from __future__ import annotations

import strawberry

from orchestrator.search.core.types import EntityType, FilterOp, UIType


@strawberry.type(description="Field that contributed most to the search result match")
class MatchingFieldType:
    text: str
    path: str
    highlight_indices: list[tuple[int, int]] | None = None


@strawberry.type(description="A single search result item")
class SearchResultType:
    entity_id: str
    entity_type: EntityType
    entity_title: str
    score: float
    perfect_match: int = 0
    matching_field: MatchingFieldType | None = None
    response_columns: strawberry.scalars.JSON | None = None


@strawberry.type(description="Metadata about the search operation performed")
class SearchMetadataType:
    search_type: str
    description: str


@strawberry.type(description="Page info for search cursor-based pagination")
class SearchPageInfoType:
    has_next_page: bool = False
    next_page_cursor: str | None = None


@strawberry.type(description="Cursor info for search pagination")
class CursorInfoType:
    total_items: int | None = None
    start_cursor: int | None = None
    end_cursor: int | None = None


@strawberry.type(description="Paginated search results")
class SearchResultsConnection:
    data: list[SearchResultType]
    page_info: SearchPageInfoType
    search_metadata: SearchMetadataType | None = None
    cursor: CursorInfoType | None = None


@strawberry.type(description="Information about a leaf (terminal field) in the entity schema")
class LeafInfoType:
    name: str
    ui_types: list[UIType]
    paths: list[str]


@strawberry.type(description="Information about a component (nested object) in the entity schema")
class ComponentInfoType:
    name: str
    ui_types: list[UIType]


@strawberry.type(description="Path autocomplete response with leaves and components")
class PathsResponseType:
    leaves: list[LeafInfoType]
    components: list[ComponentInfoType]


@strawberry.type(description="Visualization type for aggregation results")
class VisualizationTypeGql:
    type: str = "table"


@strawberry.type(description="A single result row with group values and aggregation values")
class ResultRowType:
    group_values: list[tuple[str, str]]
    aggregations: list[tuple[str, float]]


@strawberry.type(description="Tabular query results for search and aggregation rendering")
class QueryResultsResponseType:
    results: list[ResultRowType]
    total_results: int
    metadata: SearchMetadataType
    visualization_type: VisualizationTypeGql


@strawberry.type(description="Export response containing flattened entity records")
class ExportResponseType:
    page: list[strawberry.scalars.JSON]


@strawberry.type(description="Value schema for a filter operator")
class ValueSchemaType:
    operator: FilterOp
    kind: str
    fields: list[ValueSchemaType] | None = None


@strawberry.type(description="Definition of available operators and value schemas for a UI type")
class TypeDefinitionType:
    ui_type: UIType
    operators: list[FilterOp]
    value_schema: list[ValueSchemaType]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest test/unit_tests/graphql/test_search.py -k "matching_field_type or search_result_type or search_metadata_type or search_results_connection or paths_response or query_results_response or type_definition" -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/graphql/schemas/search.py test/unit_tests/graphql/test_search.py
git commit -m "feat(graphql): add Strawberry search output types"
```

---

### Task 3: Search Resolvers

**Files:**
- Create: `orchestrator/graphql/resolvers/search.py`
- Modify: `orchestrator/graphql/resolvers/__init__.py`

Each resolver maps to one REST endpoint, delegating to the existing service layer. All resolvers follow the existing pattern of using `run_in_threadpool` for DB access and returning Strawberry types.

- [ ] **Step 1: Write failing test for search resolver**

Append to `test/unit_tests/graphql/test_search.py`:

```python
import json
from http import HTTPStatus
from uuid import uuid4

from test.unit_tests.config import GRAPHQL_ENDPOINT, GRAPHQL_HEADERS


SEARCH_QUERY = """
query SearchQuery($entityType: SearchEntityType!, $input: SearchInput!) {
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
query SearchPathsQuery($prefix: String, $q: String, $entityType: SearchEntityType, $limit: Int) {
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
            groupValues
            aggregations
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


def test_search_definitions_query(test_client_graphql):
    data = json.dumps({"query": SEARCH_DEFINITIONS_QUERY})
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    definitions = result["data"]["searchDefinitions"]
    assert len(definitions) > 0
    # Should contain at least string, number, boolean, datetime, component
    ui_types = {d["uiType"] for d in definitions}
    assert "string" in ui_types or "STRING" in ui_types
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest test/unit_tests/graphql/test_search.py::test_search_definitions_query -v`
Expected: FAIL — resolver not found / field not registered

- [ ] **Step 3: Create resolvers module**

```python
# orchestrator/graphql/resolvers/search.py
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

"""GraphQL resolvers for the search subsystem."""

from __future__ import annotations

from uuid import UUID

import structlog
from graphql import GraphQLError

from orchestrator.db import SearchQueryTable, db
from orchestrator.graphql.schemas.search import (
    ComponentInfoType,
    CursorInfoType,
    ExportResponseType,
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
    VisualizationTypeGql,
)
from orchestrator.graphql.search_inputs import SearchInput
from orchestrator.graphql.types import OrchestratorInfo
from orchestrator.search.core.exceptions import InvalidCursorError, QueryStateNotFoundError
from orchestrator.search.core.types import EntityType, FilterOp, UIType
from orchestrator.search.filters.definitions import generate_definitions
from orchestrator.search.query import QueryState, engine
from orchestrator.search.query.builder import build_paths_query, create_path_autocomplete_lquery, process_path_rows
from orchestrator.search.query.queries import AggregateQuery, CountQuery, ExportQuery, QueryAdapter, SelectQuery
from orchestrator.search.query.results import SearchResult, SearchResponse, VisualizationType
from orchestrator.search.query.validation import is_lquery_syntactically_valid, validate_structured_order_by_element
from orchestrator.search.retrieval.pagination import PageCursor, encode_next_page_cursor

logger = structlog.get_logger(__name__)


def _result_to_gql(result: SearchResult) -> SearchResultType:
    """Convert a domain SearchResult to the Strawberry output type."""
    matching_field = None
    if result.matching_field:
        matching_field = MatchingFieldType(
            text=result.matching_field.text,
            path=result.matching_field.path,
            highlight_indices=result.matching_field.highlight_indices,
        )
    return SearchResultType(
        entity_id=result.entity_id,
        entity_type=result.entity_type,
        entity_title=result.entity_title,
        score=result.score,
        perfect_match=result.perfect_match,
        matching_field=matching_field,
        response_columns=result.response_columns,
    )


def _metadata_to_gql(metadata: "from orchestrator.search.core.types import SearchMetadata") -> SearchMetadataType:
    """Convert SearchMetadata dataclass to Strawberry type."""
    return SearchMetadataType(search_type=metadata.search_type, description=metadata.description)


def _build_search_results_connection(
    results: list[SearchResult],
    metadata: "from orchestrator.search.core.types import SearchMetadata",
    next_page_cursor: str | None,
    total_items: int | None,
    start_cursor: int | None,
    end_cursor: int | None,
) -> SearchResultsConnection:
    """Build a SearchResultsConnection from domain objects."""
    page_info = SearchPageInfoType(
        has_next_page=next_page_cursor is not None,
        next_page_cursor=next_page_cursor,
    )
    cursor_info = None
    if total_items is not None:
        cursor_info = CursorInfoType(
            total_items=total_items,
            start_cursor=start_cursor,
            end_cursor=end_cursor,
        )
    return SearchResultsConnection(
        data=[_result_to_gql(r) for r in results],
        page_info=page_info,
        search_metadata=_metadata_to_gql(metadata),
        cursor=cursor_info,
    )


async def resolve_search(
    info: OrchestratorInfo,
    entity_type: EntityType,
    input: SearchInput,
    cursor: str | None = None,
    include_columns: bool = True,
) -> SearchResultsConnection:
    """Unified search resolver — replaces the per-entity REST endpoints."""
    try:
        page_cursor: PageCursor | None = None
        query: SelectQuery

        if cursor:
            page_cursor = PageCursor.decode(cursor)
            query_state = QueryState.load_from_id(page_cursor.query_id, SelectQuery)
            query = query_state.query
        else:
            query = input.to_select_query(entity_type)
            validate_structured_order_by_element(entity_type, None)
            query_state = QueryState(query=query, query_embedding=None)

        if not include_columns:
            query = query.model_copy(update={"response_columns": []})

        search_response = await engine.execute_search(query, db.session, page_cursor, query_state.query_embedding)

        if not search_response.results:
            return SearchResultsConnection(
                data=[],
                page_info=SearchPageInfoType(),
                search_metadata=_metadata_to_gql(search_response.metadata),
                cursor=None,
            )

        next_page_cursor = encode_next_page_cursor(search_response, page_cursor, query)

        return _build_search_results_connection(
            results=search_response.results,
            metadata=search_response.metadata,
            next_page_cursor=next_page_cursor,
            total_items=search_response.total_items,
            start_cursor=search_response.start_cursor,
            end_cursor=search_response.end_cursor,
        )
    except (InvalidCursorError, ValueError) as e:
        raise GraphQLError(str(e), extensions={"code": "VALIDATION_ERROR"}) from e
    except QueryStateNotFoundError as e:
        raise GraphQLError(str(e), extensions={"code": "NOT_FOUND"}) from e
    except Exception as e:
        logger.error("Search failed", error=str(e))
        raise GraphQLError(f"Search failed: {e}", extensions={"code": "INTERNAL_ERROR"}) from e


async def resolve_search_paths(
    info: OrchestratorInfo,
    prefix: str = "",
    q: str | None = None,
    entity_type: EntityType = EntityType.SUBSCRIPTION,
    limit: int = 10,
) -> PathsResponseType:
    """Resolve path autocomplete suggestions."""
    try:
        if prefix:
            lquery_pattern = create_path_autocomplete_lquery(prefix)
            if not is_lquery_syntactically_valid(lquery_pattern, db.session):
                raise GraphQLError(
                    f"Prefix '{prefix}' creates an invalid search pattern.",
                    extensions={"code": "VALIDATION_ERROR"},
                )

        stmt = build_paths_query(entity_type=entity_type, prefix=prefix, q=q)
        stmt = stmt.limit(max(1, min(limit, 10)))
        rows = db.session.execute(stmt).all()

        leaves, components = process_path_rows(rows)
        return PathsResponseType(
            leaves=[LeafInfoType(name=l.name, ui_types=l.ui_types, paths=l.paths) for l in leaves],
            components=[ComponentInfoType(name=c.name, ui_types=c.ui_types) for c in components],
        )
    except GraphQLError:
        raise
    except Exception as e:
        logger.error("Search paths failed", error=str(e))
        raise GraphQLError(f"Failed to fetch paths: {e}", extensions={"code": "INTERNAL_ERROR"}) from e


def _value_schema_to_gql(vs: "from orchestrator.search.filters.definitions import ValueSchema", op: FilterOp) -> ValueSchemaType:
    """Convert a ValueSchema to Strawberry type."""
    fields = None
    if vs.fields:
        fields = [
            ValueSchemaType(operator=op, kind=sub_vs.kind if isinstance(sub_vs.kind, str) else sub_vs.kind.value, fields=None)
            for sub_vs in vs.fields.values()
        ]
    return ValueSchemaType(
        operator=op,
        kind=vs.kind if isinstance(vs.kind, str) else vs.kind.value,
        fields=fields,
    )


async def resolve_search_definitions(info: OrchestratorInfo) -> list[TypeDefinitionType]:
    """Resolve filter operator definitions for all UI types."""
    definitions = generate_definitions()
    return [
        TypeDefinitionType(
            ui_type=ui_type,
            operators=td.operators,
            value_schema=[_value_schema_to_gql(vs, op) for op, vs in td.value_schema.items()],
        )
        for ui_type, td in definitions.items()
    ]


async def resolve_search_query_results(info: OrchestratorInfo, query_id: str) -> QueryResultsResponseType:
    """Resolve full query results by query_id (aggregations, counts, or search)."""
    try:
        uid = UUID(query_id)
        row = db.session.query(SearchQueryTable).filter_by(query_id=uid).first()
        if not row:
            raise GraphQLError(f"Query {query_id} not found", extensions={"code": "NOT_FOUND"})

        query = QueryAdapter.validate_python(row.parameters)

        if isinstance(query, SelectQuery):
            embedding = list(row.query_embedding) if row.query_embedding is not None else None
            search_response = await engine.execute_search(query, db.session, query_embedding=embedding)
            result_rows = [
                ResultRowType(
                    group_values=[
                        ("entity_id", result.entity_id),
                        ("title", result.entity_title),
                        ("entity_type", result.entity_type.value),
                    ],
                    aggregations=[("score", result.score)],
                )
                for result in search_response.results
            ]
            return QueryResultsResponseType(
                results=result_rows,
                total_results=len(result_rows),
                metadata=_metadata_to_gql(search_response.metadata),
                visualization_type=VisualizationTypeGql(type="table"),
            )

        if isinstance(query, (CountQuery, AggregateQuery)):
            response = await engine.execute_aggregation(query, db.session)
            result_rows = [
                ResultRowType(
                    group_values=list(r.group_values.items()),
                    aggregations=[(k, float(v)) for k, v in r.aggregations.items()],
                )
                for r in response.results
            ]
            return QueryResultsResponseType(
                results=result_rows,
                total_results=response.total_results,
                metadata=_metadata_to_gql(response.metadata),
                visualization_type=VisualizationTypeGql(type=response.visualization_type.type),
            )

        raise GraphQLError(f"Unsupported query type: {query.query_type}", extensions={"code": "BAD_REQUEST"})
    except GraphQLError:
        raise
    except QueryStateNotFoundError as e:
        raise GraphQLError(str(e), extensions={"code": "NOT_FOUND"}) from e
    except Exception as e:
        logger.error("Failed to fetch query results", query_id=query_id, error=str(e))
        raise GraphQLError(f"Failed to fetch query results: {e}", extensions={"code": "INTERNAL_ERROR"}) from e


async def resolve_search_query(
    info: OrchestratorInfo,
    query_id: str,
    cursor: str | None = None,
) -> SearchResultsConnection:
    """Retrieve and execute a saved search by query_id."""
    try:
        page_cursor: PageCursor | None = None
        if cursor:
            page_cursor = PageCursor.decode(cursor)
            query_state = QueryState.load_from_id(page_cursor.query_id, SelectQuery)
        else:
            query_state = QueryState.load_from_id(query_id, SelectQuery)

        query = query_state.query
        search_response = await engine.execute_search(query, db.session, page_cursor, query_state.query_embedding)

        if not search_response.results:
            return SearchResultsConnection(
                data=[],
                page_info=SearchPageInfoType(),
                search_metadata=_metadata_to_gql(search_response.metadata),
                cursor=None,
            )

        next_page_cursor = encode_next_page_cursor(search_response, page_cursor, query)

        return _build_search_results_connection(
            results=search_response.results,
            metadata=search_response.metadata,
            next_page_cursor=next_page_cursor,
            total_items=search_response.total_items,
            start_cursor=search_response.start_cursor,
            end_cursor=search_response.end_cursor,
        )
    except (InvalidCursorError, ValueError) as e:
        raise GraphQLError(str(e), extensions={"code": "VALIDATION_ERROR"}) from e
    except QueryStateNotFoundError as e:
        raise GraphQLError(str(e), extensions={"code": "NOT_FOUND"}) from e
    except Exception as e:
        logger.error("Search query failed", query_id=query_id, error=str(e))
        raise GraphQLError(f"Search query failed: {e}", extensions={"code": "INTERNAL_ERROR"}) from e


async def resolve_search_query_export(
    info: OrchestratorInfo,
    query_id: str,
) -> ExportResponseType:
    """Export search results using a saved query_id."""
    try:
        query_state = QueryState.load_from_id(query_id, SelectQuery)
        export_query = ExportQuery(
            entity_type=query_state.query.entity_type,
            filters=query_state.query.filters,
            query_text=query_state.query.query_text,
        )
        export_records = await engine.execute_export(export_query, db.session, query_state.query_embedding)
        return ExportResponseType(page=export_records)
    except (ValueError, QueryStateNotFoundError) as e:
        raise GraphQLError(str(e), extensions={"code": "NOT_FOUND"}) from e
    except Exception as e:
        logger.error("Export failed", query_id=query_id, error=str(e))
        raise GraphQLError(f"Export failed: {e}", extensions={"code": "INTERNAL_ERROR"}) from e
```

- [ ] **Step 4: Update resolver __init__.py**

Add to `orchestrator/graphql/resolvers/__init__.py`:

```python
from orchestrator.graphql.resolvers.search import (
    resolve_search,
    resolve_search_definitions,
    resolve_search_paths,
    resolve_search_query,
    resolve_search_query_export,
    resolve_search_query_results,
)
```

And add these names to `__all__`.

- [ ] **Step 5: Run test to verify resolvers import correctly**

Run: `uv run python -c "from orchestrator.graphql.resolvers.search import resolve_search, resolve_search_definitions, resolve_search_paths"`
Expected: No import errors

- [ ] **Step 6: Commit**

```bash
git add orchestrator/graphql/resolvers/search.py orchestrator/graphql/resolvers/__init__.py
git commit -m "feat(graphql): add search resolvers delegating to existing engine"
```

---

### Task 4: Register Search Query in GraphQL Schema

**Files:**
- Modify: `orchestrator/graphql/schema.py`
- Modify: `orchestrator/graphql/__init__.py`

Wire the resolvers into the schema by creating a `SearchQuery` type and merging it into the root `Query`.

- [ ] **Step 1: Write failing integration test for search definitions endpoint**

The test `test_search_definitions_query` from Task 3 Step 1 should now be used. It will fail because the schema doesn't have the `searchDefinitions` field yet.

Run: `uv run pytest test/unit_tests/graphql/test_search.py::test_search_definitions_query -v`
Expected: FAIL — `Cannot query field "searchDefinitions" on type "Query"`

- [ ] **Step 2: Add SearchQuery to schema.py**

In `orchestrator/graphql/schema.py`, add imports:

```python
from orchestrator.graphql.resolvers.search import (
    resolve_search,
    resolve_search_definitions,
    resolve_search_paths,
    resolve_search_query,
    resolve_search_query_export,
    resolve_search_query_results,
)
from orchestrator.graphql.schemas.search import (
    ExportResponseType,
    PathsResponseType,
    QueryResultsResponseType,
    SearchResultsConnection,
    TypeDefinitionType,
)
from orchestrator.graphql.search_inputs import SearchInput, StrawberryEntityType
from orchestrator.search.core.types import EntityType
```

Add the new query type:

```python
@strawberry.federation.type(description="Search queries")
class SearchQuery:
    search: SearchResultsConnection = authenticated_field(
        resolver=resolve_search,
        description="Unified search across entity types",
    )
    search_paths: PathsResponseType = authenticated_field(
        resolver=resolve_search_paths,
        description="Path autocomplete suggestions for search filter UI",
    )
    search_definitions: list[TypeDefinitionType] = authenticated_field(
        resolver=resolve_search_definitions,
        description="Filter operator definitions for all UI types",
    )
    search_query_results: QueryResultsResponseType = authenticated_field(
        resolver=resolve_search_query_results,
        description="Fetch full query results by query_id (aggregations, counts, or search)",
    )
    search_query: SearchResultsConnection = authenticated_field(
        resolver=resolve_search_query,
        description="Retrieve and execute a saved search by query_id",
    )
    search_query_export: ExportResponseType = authenticated_field(
        resolver=resolve_search_query_export,
        description="Export search results using a saved query_id",
    )
```

Update the `Query` merge:

```python
Query: type = merge_types("Query", (OrchestratorQuery, CustomerQuery, SearchQuery))
```

- [ ] **Step 3: Update orchestrator/graphql/__init__.py**

Add `SearchQuery` to both the imports and `__all__`.

- [ ] **Step 4: Run the integration test**

Run: `uv run pytest test/unit_tests/graphql/test_search.py::test_search_definitions_query -v`
Expected: PASS — the `searchDefinitions` query returns definitions

- [ ] **Step 5: Commit**

```bash
git add orchestrator/graphql/schema.py orchestrator/graphql/__init__.py
git commit -m "feat(graphql): register SearchQuery in GraphQL schema"
```

---

### Task 5: Integration Tests for All Search GraphQL Endpoints

**Files:**
- Modify: `test/unit_tests/graphql/test_search.py`

Add integration tests that exercise the full GraphQL stack (schema → resolver → engine). The `searchPaths` and entity search queries require the `AiSearchIndex` table to be populated, which depends on the search extra. Tests that need the search engine should be marked with `@pytest.mark.search`.

- [ ] **Step 1: Add integration tests for searchPaths (requires search index)**

Append to `test/unit_tests/graphql/test_search.py`:

```python
@pytest.mark.search
def test_search_paths_query(test_client_graphql):
    data = json.dumps({
        "query": SEARCH_PATHS_QUERY,
        "variables": {
            "entityType": "SUBSCRIPTION",
            "limit": 5,
        },
    })
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    paths_data = result["data"]["searchPaths"]
    assert "leaves" in paths_data
    assert "components" in paths_data


@pytest.mark.search
def test_search_subscriptions(test_client_graphql):
    data = json.dumps({
        "query": SEARCH_QUERY,
        "variables": {
            "entityType": "SUBSCRIPTION",
            "input": {
                "limit": 5,
            },
        },
    })
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
    search_data = result["data"]["search"]
    assert "data" in search_data
    assert "pageInfo" in search_data
    assert "searchMetadata" in search_data


@pytest.mark.search
def test_search_with_filters(test_client_graphql):
    data = json.dumps({
        "query": SEARCH_QUERY,
        "variables": {
            "entityType": "SUBSCRIPTION",
            "input": {
                "filters": {
                    "op": "AND",
                    "filters": [
                        {
                            "path": "subscription.status",
                            "condition": {"op": "eq", "value": "active"},
                            "valueKind": "string",
                        },
                    ],
                    "groups": [],
                },
                "limit": 10,
            },
        },
    })
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result


@pytest.mark.search
def test_search_with_text_query(test_client_graphql):
    data = json.dumps({
        "query": SEARCH_QUERY,
        "variables": {
            "entityType": "SUBSCRIPTION",
            "input": {
                "query": "test",
                "limit": 5,
            },
        },
    })
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result


@pytest.mark.search
@pytest.mark.parametrize(
    "entity_type",
    [
        pytest.param("SUBSCRIPTION", id="subscriptions"),
        pytest.param("PRODUCT", id="products"),
        pytest.param("WORKFLOW", id="workflows"),
        pytest.param("PROCESS", id="processes"),
    ],
)
def test_search_all_entity_types(test_client_graphql, entity_type):
    data = json.dumps({
        "query": SEARCH_QUERY,
        "variables": {
            "entityType": entity_type,
            "input": {"limit": 5},
        },
    })
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
```

- [ ] **Step 2: Add error handling tests**

Append to `test/unit_tests/graphql/test_search.py`:

```python
def test_search_query_not_found(test_client_graphql):
    data = json.dumps({
        "query": SEARCH_QUERY_BY_ID,
        "variables": {
            "queryId": str(uuid4()),
        },
    })
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert result.get("errors") is not None


def test_search_query_results_not_found(test_client_graphql):
    data = json.dumps({
        "query": SEARCH_QUERY_RESULTS,
        "variables": {
            "queryId": str(uuid4()),
        },
    })
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert result.get("errors") is not None


def test_search_query_export_not_found(test_client_graphql):
    data = json.dumps({
        "query": SEARCH_QUERY_EXPORT,
        "variables": {
            "queryId": str(uuid4()),
        },
    })
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert result.get("errors") is not None


def test_search_invalid_limit(test_client_graphql):
    """Limit validation happens at SelectQuery level (1-30)."""
    data = json.dumps({
        "query": SEARCH_QUERY,
        "variables": {
            "entityType": "SUBSCRIPTION",
            "input": {"limit": 100},
        },
    })
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers=GRAPHQL_HEADERS)
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    # The error may come from Pydantic validation in SelectQuery
    assert result.get("errors") is not None
```

- [ ] **Step 3: Run all search tests**

Run: `uv run pytest test/unit_tests/graphql/test_search.py -v`
Expected: Unit tests PASS, integration tests that require search index marked with `@pytest.mark.search` may be skipped depending on test environment

- [ ] **Step 4: Commit**

```bash
git add test/unit_tests/graphql/test_search.py
git commit -m "test(graphql): add integration tests for search GraphQL endpoints"
```

---

### Task 6: Type Check and Lint

**Files:**
- Potentially modify any files with type/lint issues

- [ ] **Step 1: Run mypy on new files**

Run: `uv run mypy orchestrator/graphql/search_inputs.py orchestrator/graphql/schemas/search.py orchestrator/graphql/resolvers/search.py`
Expected: No errors (or fix any that appear)

- [ ] **Step 2: Run ruff on new files**

Run: `uv run ruff check orchestrator/graphql/search_inputs.py orchestrator/graphql/schemas/search.py orchestrator/graphql/resolvers/search.py`
Expected: No errors (or fix any that appear)

- [ ] **Step 3: Run ruff format**

Run: `uv run ruff format orchestrator/graphql/search_inputs.py orchestrator/graphql/schemas/search.py orchestrator/graphql/resolvers/search.py`

- [ ] **Step 4: Run full test suite on graphql**

Run: `uv run pytest test/unit_tests/graphql/ -v`
Expected: All existing tests still pass, new tests pass

- [ ] **Step 5: Commit if any fixes were needed**

```bash
git add -u
git commit -m "fix(graphql): resolve type check and lint issues in search types"
```
