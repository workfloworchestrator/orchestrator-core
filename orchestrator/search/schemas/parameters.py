import uuid
from typing import Any, Dict, Literal, Optional, Type

from pydantic import BaseModel, ConfigDict, Field

from orchestrator.search.core.types import ActionType, EntityKind
from orchestrator.search.filters import FilterSet


class BaseSearchParameters(BaseModel):
    """Base model with common search parameters."""

    action: ActionType = Field(default=ActionType.SELECT, description="The action to perform.")
    entity_type: EntityKind

    filters: Optional[FilterSet] = Field(
        default=None, description="A list of structured filters to apply to the search."
    )

    query: Optional[str] = Field(
        default=None, description="Unified search query - will be processed into vector_query and/or fuzzy_term"
    )

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def create(cls, entity_type: EntityKind, **kwargs: Any) -> "BaseSearchParameters":
        try:
            return PARAMETER_REGISTRY[entity_type](entity_type=entity_type, **kwargs)
        except KeyError:
            raise ValueError(f"No search parameter class found for entity type: {entity_type.value}")

    @property
    def vector_query(self) -> Optional[str]:
        """Extract vector query from unified query field."""
        if not self.query:
            return None
        try:
            uuid.UUID(self.query)
            return None  # It's a UUID, so disable vector search.
        except ValueError:
            return self.query

    @property
    def fuzzy_term(self) -> Optional[str]:
        """Extract fuzzy term from unified query field."""
        if not self.query:
            return None

        words = self.query.split()
        # Only use fuzzy for single words
        return self.query if len(words) == 1 else None


class SubscriptionSearchParameters(BaseSearchParameters):
    entity_type: Literal[EntityKind.SUBSCRIPTION] = Field(
        default=EntityKind.SUBSCRIPTION, description="The type of entity to search."
    )
    model_config = ConfigDict(
        json_schema_extra={
            "title": "SearchSubscriptions",
            "description": "Search subscriptions based on specific criteria.",
            "examples": [
                {
                    "filters": [
                        {"path": "subscription.status", "condition": {"op": "eq", "value": "provisioning"}},
                        {"path": "subscription.end_date", "condition": {"op": "gte", "value": "2025-01-01"}},
                    ]
                }
            ],
        }
    )


class ProductSearchParameters(BaseSearchParameters):
    entity_type: Literal[EntityKind.PRODUCT] = Field(
        default=EntityKind.PRODUCT, description="The type of entity to search."
    )
    model_config = ConfigDict(
        json_schema_extra={
            "title": "SearchProducts",
            "description": "Search products based on specific criteria.",
            "examples": [
                {
                    "filters": [
                        {"path": "product.product_type", "condition": {"op": "eq", "value": "Shop"}},
                    ]
                }
            ],
        }
    )


class WorkflowSearchParameters(BaseSearchParameters):
    entity_type: Literal[EntityKind.WORKFLOW] = Field(
        default=EntityKind.WORKFLOW, description="The type of entity to search."
    )


class ProcessSearchParameters(BaseSearchParameters):
    """Search parameters specifically for PROCESS entities."""

    entity_type: Literal[EntityKind.PROCESS] = Field(
        default=EntityKind.PROCESS, description="The type of entity to search."
    )


PARAMETER_REGISTRY: Dict[EntityKind, Type[BaseSearchParameters]] = {
    EntityKind.SUBSCRIPTION: SubscriptionSearchParameters,
    EntityKind.PRODUCT: ProductSearchParameters,
    EntityKind.WORKFLOW: WorkflowSearchParameters,
    EntityKind.PROCESS: ProcessSearchParameters,
}
