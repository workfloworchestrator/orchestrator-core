from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from orchestrator.search.schemas.results import Highlight, PathInfo

T = TypeVar("T")


class PageInfoSchema(BaseModel):
    total_items: int = Field(default=0, alias="totalItems")
    start_cursor: int = Field(default=0, alias="startCursor")
    has_previous_page: bool = Field(default=False, alias="hasPreviousPage")
    has_next_page: bool = Field(default=False, alias="hasNextPage")
    end_cursor: int = Field(default=0, alias="endCursor")
    sort_fields: list[str] = Field(default_factory=list, alias="sortFields")
    filter_fields: list[str] = Field(default_factory=list, alias="filterFields")


class ProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str
    tag: str
    product_type: str = Field(alias="productType")


class SubscriptionSearchResult(BaseModel):
    score: float
    highlight: Highlight | None = None

    subscription: dict[str, Any]


class ConnectionSchema(BaseModel, Generic[T]):
    page: list[T]
    page_info: PageInfoSchema = Field(alias="pageInfo")

    model_config = ConfigDict(populate_by_name=True)


class WorkflowProductSchema(BaseModel):
    """Product associated with a workflow."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    product_type: str = Field(alias="productType")
    product_id: UUID = Field(alias="productId")
    name: str


class WorkflowSearchSchema(BaseModel):
    """Schema for workflow search results."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str
    products: list[WorkflowProductSchema]
    description: str | None = None
    created_at: datetime | None = Field(alias="createdAt", default=None)


class ProductSearchSchema(BaseModel):
    """Schema for product search results."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    product_id: UUID = Field(alias="productId")
    name: str
    product_type: str = Field(alias="productType")
    tag: str | None = None
    description: str | None = None
    status: str | None = None
    created_at: datetime | None = Field(alias="createdAt", default=None)


class ProcessSearchSchema(BaseModel):
    """Schema for process search results."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    process_id: UUID = Field(alias="processId")
    workflow_name: str = Field(alias="workflowName")
    workflow_id: UUID = Field(alias="workflowId")
    status: str = Field(alias="last_status")
    is_task: bool = Field(alias="isTask")
    created_by: str | None = Field(alias="createdBy", default=None)
    started_at: datetime = Field(alias="startedAt")
    last_modified_at: datetime = Field(alias="lastModifiedAt")
    last_step: str | None = Field(alias="lastStep", default=None)
    failed_reason: str | None = Field(alias="failedReason", default=None)
    subscription_ids: list[UUID] | None = Field(alias="subscriptionIds", default=None)


class PathsResponse(BaseModel):
    prefix: str
    paths: list[PathInfo]

    model_config = ConfigDict(extra="forbid", use_enum_values=True)
