from orchestrator.db import (
    ProcessTable,
    ProductTable,
    SubscriptionTable,
    WorkflowTable,
)
from orchestrator.search.core.types import EntityConfig, EntityKind

from .traverse import (
    ProcessTraverser,
    ProductTraverser,
    SubscriptionTraverser,
    WorkflowTraverser,
)

ENTITY_CONFIG_REGISTRY: dict[EntityKind, EntityConfig] = {
    EntityKind.SUBSCRIPTION: EntityConfig(
        entity_kind=EntityKind.SUBSCRIPTION,
        table=SubscriptionTable,
        traverser=SubscriptionTraverser,
        pk_name="subscription_id",
        root_name="subscription",
    ),
    EntityKind.PRODUCT: EntityConfig(
        entity_kind=EntityKind.PRODUCT,
        table=ProductTable,
        traverser=ProductTraverser,
        pk_name="product_id",
        root_name="product",
    ),
    EntityKind.PROCESS: EntityConfig(
        entity_kind=EntityKind.PROCESS,
        table=ProcessTable,
        traverser=ProcessTraverser,
        pk_name="process_id",
        root_name="process",
    ),
    EntityKind.WORKFLOW: EntityConfig(
        entity_kind=EntityKind.WORKFLOW,
        table=WorkflowTable,
        traverser=WorkflowTraverser,
        pk_name="workflow_id",
        root_name="workflow",
    ),
}
