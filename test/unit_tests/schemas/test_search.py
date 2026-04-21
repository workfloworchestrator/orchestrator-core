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

"""Tests for search-related schemas: default factories, extra-field rejection, and enum serialization."""

import pytest
from pydantic import ValidationError

from orchestrator.core.schemas.search import (
    ExportResponse,
    PageInfoSchema,
    PathsResponse,
    SearchResultsSchema,
)
from orchestrator.core.search.core.types import UIType
from orchestrator.core.search.query.builder import LeafInfo


def test_search_results_data_default_factory_creates_independent_lists() -> None:
    a: SearchResultsSchema[str] = SearchResultsSchema()
    b: SearchResultsSchema[str] = SearchResultsSchema()
    a.data.append("item")
    assert b.data == []


def test_search_results_page_info_default_factory_creates_independent_instances() -> None:
    a: SearchResultsSchema[str] = SearchResultsSchema()
    b: SearchResultsSchema[str] = SearchResultsSchema()
    assert a.page_info is not b.page_info


def test_search_results_defaults() -> None:
    schema: SearchResultsSchema[str] = SearchResultsSchema()
    assert schema.data == []
    assert isinstance(schema.page_info, PageInfoSchema)
    assert schema.page_info.has_next_page is False
    assert schema.search_metadata is None
    assert schema.cursor is None


@pytest.mark.parametrize(
    "model,kwargs",
    [
        pytest.param(PathsResponse, {"leaves": [], "components": [], "extra_field": "no"}, id="paths-extra"),
        pytest.param(ExportResponse, {"page": [], "extra": "no"}, id="export-extra"),
    ],
)
def test_extra_fields_forbidden(model: type, kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        model(**kwargs)


def test_paths_response_serializes_enum_values_as_strings() -> None:
    leaf = LeafInfo(name="ts", ui_types=[UIType.DATETIME], paths=["a.ts"])
    schema = PathsResponse(leaves=[leaf], components=[])
    assert schema.leaves[0].ui_types == ["datetime"]
