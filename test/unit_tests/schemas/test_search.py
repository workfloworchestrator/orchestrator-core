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

import types

import pytest
from pydantic import ValidationError

from orchestrator.schemas.search import (
    CursorInfoSchema,
    ExportResponse,
    PageInfoSchema,
    PathsResponse,
    ProductSchema,
    SearchResultsSchema,
)
from orchestrator.search.core.types import SearchMetadata, UIType
from orchestrator.search.query.builder import ComponentInfo, LeafInfo


class TestPageInfoSchema:
    def test_default_instantiation_has_expected_defaults(self) -> None:
        schema = PageInfoSchema()
        assert schema.has_next_page is False
        assert schema.next_page_cursor is None

    def test_instantiate_with_has_next_page_true_succeeds(self) -> None:
        schema = PageInfoSchema(has_next_page=True)
        assert schema.has_next_page is True

    def test_instantiate_with_cursor_succeeds(self) -> None:
        schema = PageInfoSchema(has_next_page=True, next_page_cursor="cursor_abc")
        assert schema.next_page_cursor == "cursor_abc"

    def test_instantiate_with_all_fields_succeeds(self) -> None:
        schema = PageInfoSchema(has_next_page=True, next_page_cursor="next_token")
        assert schema.has_next_page is True
        assert schema.next_page_cursor == "next_token"

    @pytest.mark.parametrize(
        "field,value",
        [
            ("has_next_page", "not_a_bool"),
            ("next_page_cursor", 12345),
        ],
        ids=["has_next_page_wrong_type", "next_page_cursor_wrong_type"],
    )
    def test_wrong_type_raises_validation_error(self, field: str, value: object) -> None:
        with pytest.raises(ValidationError):
            PageInfoSchema(**{field: value})  # type: ignore[arg-type]


class TestProductSchema:
    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = ProductSchema(name="My Product", tag="MP", product_type="Ethernet")
        assert schema.name == "My Product"
        assert schema.tag == "MP"
        assert schema.product_type == "Ethernet"

    @pytest.mark.parametrize(
        "missing_field",
        ["name", "tag", "product_type"],
        ids=["missing_name", "missing_tag", "missing_product_type"],
    )
    def test_missing_required_field_raises_validation_error(self, missing_field: str) -> None:
        data = {"name": "Product", "tag": "P", "product_type": "SomeType"}
        del data[missing_field]
        with pytest.raises(ValidationError):
            ProductSchema(**data)

    def test_from_attributes_with_namespace_object_succeeds(self) -> None:
        orm_obj = types.SimpleNamespace(name="ORM Product", tag="ORM", product_type="IP")
        schema = ProductSchema.model_validate(orm_obj, from_attributes=True)
        assert schema.name == "ORM Product"
        assert schema.tag == "ORM"
        assert schema.product_type == "IP"


class TestCursorInfoSchema:
    def test_default_instantiation_all_none(self) -> None:
        schema = CursorInfoSchema()
        assert schema.total_items is None
        assert schema.start_cursor is None
        assert schema.end_cursor is None

    def test_instantiate_with_all_values_succeeds(self) -> None:
        schema = CursorInfoSchema(total_items=100, start_cursor=0, end_cursor=99)
        assert schema.total_items == 100
        assert schema.start_cursor == 0
        assert schema.end_cursor == 99

    def test_instantiate_with_partial_values_succeeds(self) -> None:
        schema = CursorInfoSchema(total_items=50)
        assert schema.total_items == 50
        assert schema.start_cursor is None
        assert schema.end_cursor is None

    @pytest.mark.parametrize(
        "field,value",
        [
            ("total_items", 10),
            ("start_cursor", 5),
            ("end_cursor", 20),
        ],
        ids=["total_items_set", "start_cursor_set", "end_cursor_set"],
    )
    def test_individual_field_set_others_none(self, field: str, value: int) -> None:
        schema = CursorInfoSchema(**{field: value})
        assert getattr(schema, field) == value
        for other in {"total_items", "start_cursor", "end_cursor"} - {field}:
            assert getattr(schema, other) is None


class TestSearchResultsSchema:
    def test_default_instantiation_has_expected_defaults(self) -> None:
        schema: SearchResultsSchema[str] = SearchResultsSchema()
        assert schema.data == []
        assert isinstance(schema.page_info, PageInfoSchema)
        assert schema.page_info.has_next_page is False
        assert schema.search_metadata is None
        assert schema.cursor is None

    def test_instantiate_with_data_items_succeeds(self) -> None:
        schema: SearchResultsSchema[str] = SearchResultsSchema(data=["item1", "item2"])
        assert len(schema.data) == 2
        assert schema.data[0] == "item1"

    def test_instantiate_with_page_info_succeeds(self) -> None:
        page_info = PageInfoSchema(has_next_page=True, next_page_cursor="tok")
        schema: SearchResultsSchema[str] = SearchResultsSchema(data=[], page_info=page_info)
        assert schema.page_info.has_next_page is True
        assert schema.page_info.next_page_cursor == "tok"

    def test_instantiate_with_search_metadata_succeeds(self) -> None:
        metadata = SearchMetadata(search_type="structured", description="filter-based search")
        schema: SearchResultsSchema[str] = SearchResultsSchema(search_metadata=metadata)
        assert schema.search_metadata is not None
        assert schema.search_metadata.search_type == "structured"
        assert schema.search_metadata.description == "filter-based search"

    def test_instantiate_with_cursor_succeeds(self) -> None:
        cursor = CursorInfoSchema(total_items=42, start_cursor=0, end_cursor=41)
        schema: SearchResultsSchema[str] = SearchResultsSchema(cursor=cursor)
        assert schema.cursor is not None
        assert schema.cursor.total_items == 42

    def test_instantiate_with_all_fields_populated_succeeds(self) -> None:
        metadata = SearchMetadata(search_type="fuzzy", description="trigram search")
        cursor = CursorInfoSchema(total_items=5, start_cursor=0, end_cursor=4)
        page_info = PageInfoSchema(has_next_page=False)
        schema: SearchResultsSchema[dict] = SearchResultsSchema(
            data=[{"key": "value"}],
            page_info=page_info,
            search_metadata=metadata,
            cursor=cursor,
        )
        assert len(schema.data) == 1
        assert schema.search_metadata.search_type == "fuzzy"  # type: ignore[union-attr]
        assert schema.cursor.total_items == 5  # type: ignore[union-attr]

    def test_data_default_factory_creates_independent_lists(self) -> None:
        schema_a: SearchResultsSchema[str] = SearchResultsSchema()
        schema_b: SearchResultsSchema[str] = SearchResultsSchema()
        schema_a.data.append("item")
        assert schema_b.data == []

    def test_page_info_default_factory_creates_independent_instances(self) -> None:
        schema_a: SearchResultsSchema[str] = SearchResultsSchema()
        schema_b: SearchResultsSchema[str] = SearchResultsSchema()
        assert schema_a.page_info is not schema_b.page_info


class TestLeafInfoAndComponentInfo:
    def test_leaf_info_valid_instantiation(self) -> None:
        leaf = LeafInfo(name="status", ui_types=[UIType.STRING], paths=["subscription.status"])
        assert leaf.name == "status"
        assert leaf.paths == ["subscription.status"]

    def test_leaf_info_multiple_ui_types(self) -> None:
        leaf = LeafInfo(name="value", ui_types=[UIType.STRING, UIType.NUMBER], paths=["a.b"])
        assert len(leaf.ui_types) == 2

    def test_leaf_info_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LeafInfo(name="x", ui_types=[UIType.STRING], paths=[], unexpected="extra")  # type: ignore[call-arg]

    def test_leaf_info_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            LeafInfo(ui_types=[UIType.STRING], paths=[])  # type: ignore[call-arg]

    def test_component_info_valid_instantiation(self) -> None:
        comp = ComponentInfo(name="block", ui_types=[UIType.COMPONENT])
        assert comp.name == "block"
        assert comp.ui_types == ["component"]

    def test_component_info_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComponentInfo(name="block", ui_types=[UIType.COMPONENT], extra="field")  # type: ignore[call-arg]


class TestPathsResponse:
    def test_instantiate_with_leaves_and_components_succeeds(self) -> None:
        leaf = LeafInfo(name="status", ui_types=[UIType.STRING], paths=["subscription.status"])
        comp = ComponentInfo(name="block", ui_types=[UIType.COMPONENT])
        schema = PathsResponse(leaves=[leaf], components=[comp])
        assert len(schema.leaves) == 1
        assert len(schema.components) == 1

    def test_instantiate_with_empty_lists_succeeds(self) -> None:
        schema = PathsResponse(leaves=[], components=[])
        assert schema.leaves == []
        assert schema.components == []

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PathsResponse(leaves=[], components=[], extra_field="not_allowed")  # type: ignore[call-arg]

    def test_missing_leaves_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            PathsResponse(components=[])  # type: ignore[call-arg]

    def test_missing_components_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            PathsResponse(leaves=[])  # type: ignore[call-arg]

    def test_use_enum_values_stores_string_values(self) -> None:
        leaf = LeafInfo(name="ts", ui_types=[UIType.DATETIME], paths=["a.ts"])
        schema = PathsResponse(leaves=[leaf], components=[])
        assert schema.leaves[0].ui_types == ["datetime"]


class TestExportResponse:
    def test_instantiate_with_data_succeeds(self) -> None:
        schema = ExportResponse(page=[{"id": "1", "name": "sub"}])
        assert len(schema.page) == 1
        assert schema.page[0]["id"] == "1"

    def test_instantiate_with_empty_page_succeeds(self) -> None:
        schema = ExportResponse(page=[])
        assert schema.page == []

    def test_instantiate_with_multiple_records_succeeds(self) -> None:
        records = [{"key": str(i)} for i in range(5)]
        schema = ExportResponse(page=records)
        assert len(schema.page) == 5

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExportResponse(page=[], extra="not_allowed")  # type: ignore[call-arg]

    def test_missing_page_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ExportResponse()  # type: ignore[call-arg]
