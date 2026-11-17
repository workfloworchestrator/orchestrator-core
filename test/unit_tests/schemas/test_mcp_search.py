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

"""Tests for the search-engine MCP tool requests: nested arguments may arrive as JSON text."""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from orchestrator.core.schemas.mcp_search import AggregateToolRequest, SearchToolRequest
from orchestrator.core.search.filters import FilterTree

FILTER_TREE = {
    "op": "AND",
    "children": [{"path": "subscription.status", "condition": {"op": "eq", "value": "active"}, "value_kind": "string"}],
}
COUNT = {"type": "count", "alias": "n"}


@pytest.mark.parametrize(
    "model,field,value",
    [
        pytest.param(SearchToolRequest, "filters", FILTER_TREE, id="search-filters"),
        pytest.param(AggregateToolRequest, "filters", FILTER_TREE, id="aggregate-filters"),
        pytest.param(AggregateToolRequest, "group_by", ["subscription.status"], id="aggregate-group-by"),
        pytest.param(AggregateToolRequest, "aggregations", [COUNT], id="aggregate-aggregations"),
    ],
)
def test_json_text_is_the_same_as_the_object(model: Any, field: str, value: Any) -> None:
    base = {"entity_type": "SUBSCRIPTION", "query_text": "x"}

    as_object = model.model_validate({**base, field: value})
    as_text = model.model_validate({**base, field: json.dumps(value)})

    assert as_text == as_object
    assert getattr(as_text, field) is not None


def test_json_text_filters_become_a_filter_tree() -> None:
    request = SearchToolRequest.model_validate({"entity_type": "SUBSCRIPTION", "filters": json.dumps(FILTER_TREE)})

    assert isinstance(request.filters, FilterTree)
    assert request.filters.op == "AND"


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("{not json", id="malformed-json"),
        pytest.param("active", id="plain-text"),
        pytest.param("42", id="json-scalar"),
        pytest.param('"text"', id="json-string"),
        pytest.param(json.dumps({"op": "AND"}), id="json-object-of-the-wrong-shape"),
        pytest.param("[" * 100_000 + "]" * 100_000, id="nested-deeper-than-json-can-parse"),
    ],
)
def test_text_that_is_not_a_filter_tree_is_still_rejected(value: str) -> None:
    with pytest.raises(ValidationError) as error:
        SearchToolRequest.model_validate({"entity_type": "SUBSCRIPTION", "filters": value})

    assert error.value.errors()[0]["loc"][0] == "filters"


@pytest.mark.parametrize("model", [SearchToolRequest, AggregateToolRequest])
def test_the_generated_schema_still_describes_an_object(model: Any) -> None:
    schema = json.dumps(model.model_json_schema()["properties"]["filters"])

    assert "FilterTree" in schema
    assert '"string"' not in schema
