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

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from orchestrator.search.core.types import SearchMetadata
from orchestrator.search.query.builder import ComponentInfo, LeafInfo

T = TypeVar("T")


class PageInfoSchema(BaseModel):
    has_next_page: bool = False
    next_page_cursor: str | None = None


class ProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    tag: str
    product_type: str


class SearchResultsSchema(BaseModel, Generic[T]):
    data: list[T] = Field(default_factory=list)
    page_info: PageInfoSchema = Field(default_factory=PageInfoSchema)
    search_metadata: SearchMetadata | None = None


class PathsResponse(BaseModel):
    leaves: list[LeafInfo]
    components: list[ComponentInfo]

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class ExportResponse(BaseModel):
    page: list[dict]

    model_config = ConfigDict(extra="forbid")
