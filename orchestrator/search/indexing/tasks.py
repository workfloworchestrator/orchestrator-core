import uuid
from typing import Optional, Sequence

import structlog

from orchestrator.db import ProcessTable, ProductTable, SubscriptionTable, WorkflowTable, db
from orchestrator.db.database import BaseModel
from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.exceptions import SearchUtilsError
from orchestrator.search.core.types import EntityConfig, EntityKind
from orchestrator.search.indexing.common import index_entity
from orchestrator.search.indexing.registry import ENTITY_CONFIG_REGISTRY

logger = structlog.get_logger(__name__)


def _process_entities(rows: Sequence[BaseModel], config: EntityConfig, dry_run: bool, force_index: bool) -> None:
    """Process and index a list of entities."""
    for entity in rows:
        try:
            index_entity(
                entity=entity,
                entity_kind=config.entity_kind,
                traverser=config.traverser,
                index_model=AiSearchIndex,
                pk_name=config.pk_name,
                root_name=config.root_name,
                dry=dry_run,
                force_index=force_index,
            )
        except SearchUtilsError as e:
            logger.error(
                f"Skipping {config.root_name} due to indexing error",
                **{config.pk_name: str(getattr(entity, config.pk_name))},
                error=str(e),
            )

    if not dry_run:
        db.session.commit()


def index_products(
    product_id: Optional[str] = None,
    dry_run: bool = False,
    force_index: bool = False,
) -> None:
    """Re-index products in hybrid search columns."""

    rows = (
        ProductTable.query.filter(ProductTable.product_id == uuid.UUID(product_id)).all()
        if product_id
        else ProductTable.query.all()
    )

    config = ENTITY_CONFIG_REGISTRY[EntityKind.PRODUCT]
    _process_entities(rows, config, dry_run, force_index)


def index_subscriptions(
    subscription_id: Optional[str] = None, dry_run: bool = False, force_index: bool = False
) -> None:
    """Re-index subscriptions in the search index."""
    rows = (
        SubscriptionTable.query.filter(SubscriptionTable.subscription_id == uuid.UUID(subscription_id)).all()
        if subscription_id
        else SubscriptionTable.query.all()
    )
    config = ENTITY_CONFIG_REGISTRY[EntityKind.SUBSCRIPTION]
    _process_entities(rows, config, dry_run, force_index)


def index_workflows(workflow_id: Optional[str] = None, dry_run: bool = False, force_index: bool = False) -> None:
    """Re-index workflows in the search index."""
    query = WorkflowTable.select()  # Filter out deleted workflows
    if workflow_id:
        query = query.filter(WorkflowTable.workflow_id == uuid.UUID(workflow_id))
    rows = db.session.execute(query).scalars().all()
    config = ENTITY_CONFIG_REGISTRY[EntityKind.WORKFLOW]
    _process_entities(rows, config, dry_run, force_index)


def index_processes(process_id: Optional[str] = None, dry_run: bool = False, force_index: bool = False) -> None:
    """Re-index processes in hybrid search columns."""
    rows = (
        ProcessTable.query.filter(ProcessTable.process_id == uuid.UUID(process_id)).all()
        if process_id
        else ProcessTable.query.all()
    )
    config = ENTITY_CONFIG_REGISTRY[EntityKind.PROCESS]
    _process_entities(rows, config, dry_run, force_index)
