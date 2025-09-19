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

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from orchestrator.search.core.types import SearchMetadata
from orchestrator.search.schemas.results import ComponentInfo, LeafInfo, MatchingField

T = TypeVar("T")


class PageInfoSchema(BaseModel):
    has_next_page: bool = False
    next_page_cursor: str | None = None


class ProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    tag: str
    product_type: str


class SubscriptionSearchResult(BaseModel):
    score: float
    perfect_match: int
    matching_field: MatchingField | None = None
    subscription: dict[str, Any]


class SearchResultsSchema(BaseModel, Generic[T]):
    data: list[T] = Field(default_factory=list)
    page_info: PageInfoSchema = Field(default_factory=PageInfoSchema)
    search_metadata: SearchMetadata | None = None


class WorkflowProductSchema(BaseModel):
    """Product associated with a workflow."""

    model_config = ConfigDict(from_attributes=True)

    product_type: str
    product_id: UUID
    name: str


class WorkflowSearchSchema(BaseModel):
    """Schema for workflow search results."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    products: list[WorkflowProductSchema]
    description: str | None = None
    created_at: datetime | None = None


class ProductSearchSchema(BaseModel):
    """Schema for product search results."""

    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    name: str
    product_type: str
    tag: str | None = None
    description: str | None = None
    status: str | None = None
    created_at: datetime | None = None


class ProcessSearchSchema(BaseModel):
    """Schema for process search results."""

    model_config = ConfigDict(from_attributes=True)

    process_id: UUID
    workflow_name: str
    workflow_id: UUID
    last_status: str
    is_task: bool
    created_by: str | None = None
    started_at: datetime
    last_modified_at: datetime
    last_step: str | None = None
    failed_reason: str | None = None
    subscription_ids: list[UUID] | None = None


class WorkflowSearchResult(BaseModel):
    score: float
    perfect_match: int
    matching_field: MatchingField | None = None
    workflow: WorkflowSearchSchema


class ProductSearchResult(BaseModel):
    score: float
    perfect_match: int
    matching_field: MatchingField | None = None
    product: ProductSearchSchema


class ProcessSearchResult(BaseModel):
    score: float
    perfect_match: int
    matching_field: MatchingField | None = None
    process: ProcessSearchSchema


class PathsResponse(BaseModel):
    leaves: list[LeafInfo]
    components: list[ComponentInfo]

    model_config = ConfigDict(extra="forbid", use_enum_values=True)
