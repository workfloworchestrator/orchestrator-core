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

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from orchestrator.core.db import (
    ProcessTable,
    ProductBlockTable,
    ProductTable,
    ResourceTypeTable,
    SubscriptionTable,
    WorkflowTable,
    db,
)
from orchestrator.core.db.models import ProductBlockRelationTable
from orchestrator.core.search.core.types import EntityType


def fetch_subscription_export_data(entity_ids: list[str]) -> list[dict]:
    """Fetch subscription data for export.

    Args:
        entity_ids: List of subscription IDs as strings

    Returns:
        List of flattened subscription dictionaries with fields:
        subscription_id, description, status, insync, start_date, end_date,
        note, product_name, tag, product_type, customer_id
    """
    stmt = (
        select(
            SubscriptionTable.subscription_id,
            SubscriptionTable.description,
            SubscriptionTable.status,
            SubscriptionTable.insync,
            SubscriptionTable.start_date,
            SubscriptionTable.end_date,
            SubscriptionTable.note,
            SubscriptionTable.customer_id,
            ProductTable.name.label("product_name"),
            ProductTable.tag,
            ProductTable.product_type,
        )
        .join(ProductTable, SubscriptionTable.product_id == ProductTable.product_id)
        .filter(SubscriptionTable.subscription_id.in_([UUID(sid) for sid in entity_ids]))
    )

    rows = db.session.execute(stmt).all()

    return [
        {
            "subscription_id": str(row.subscription_id),
            "description": row.description,
            "status": row.status,
            "insync": row.insync,
            "start_date": row.start_date.isoformat() if row.start_date else None,
            "end_date": row.end_date.isoformat() if row.end_date else None,
            "note": row.note,
            "product_name": row.product_name,
            "tag": row.tag,
            "product_type": row.product_type,
            "customer_id": row.customer_id,
        }
        for row in rows
    ]


def fetch_workflow_export_data(entity_ids: list[str]) -> list[dict]:
    """Fetch workflow data for export.

    Args:
        entity_ids: List of workflow names as strings

    Returns:
        List of flattened workflow dictionaries with fields:
        name, description, created_at, product_names (comma-separated),
        product_ids (comma-separated), product_types (comma-separated)
    """
    stmt = (
        select(WorkflowTable).options(selectinload(WorkflowTable.products)).filter(WorkflowTable.name.in_(entity_ids))
    )
    workflows = db.session.scalars(stmt).all()

    return [
        {
            "name": w.name,
            "description": w.description,
            "created_at": w.created_at.isoformat() if w.created_at else None,
            "product_names": ", ".join(p.name for p in w.products),
            "product_ids": ", ".join(str(p.product_id) for p in w.products),
            "product_types": ", ".join(p.product_type for p in w.products),
        }
        for w in workflows
    ]


def fetch_product_export_data(entity_ids: list[str]) -> list[dict]:
    """Fetch product data for export.

    Args:
        entity_ids: List of product IDs as strings

    Returns:
        List of flattened product dictionaries with fields:
        product_id, name, product_type, tag, description, status, created_at
    """
    stmt = (
        select(ProductTable)
        .options(
            selectinload(ProductTable.workflows),
            selectinload(ProductTable.fixed_inputs),
            selectinload(ProductTable.product_blocks),
        )
        .filter(ProductTable.product_id.in_([UUID(pid) for pid in entity_ids]))
    )
    products = db.session.scalars(stmt).all()

    return [
        {
            "product_id": str(p.product_id),
            "name": p.name,
            "product_type": p.product_type,
            "tag": p.tag,
            "description": p.description,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in products
    ]


def fetch_process_export_data(entity_ids: list[str]) -> list[dict]:
    """Fetch process data for export.

    Args:
        entity_ids: List of process IDs as strings

    Returns:
        List of flattened process dictionaries with fields:
        process_id, workflow_name, workflow_id, last_status, is_task,
        created_by, started_at, last_modified_at, last_step
    """
    stmt = (
        select(ProcessTable)
        .options(selectinload(ProcessTable.workflow))
        .filter(ProcessTable.process_id.in_([UUID(pid) for pid in entity_ids]))
    )
    processes = db.session.scalars(stmt).all()

    return [
        {
            "process_id": str(p.process_id),
            "workflow_name": p.workflow.name if p.workflow else None,
            "workflow_id": str(p.workflow_id),
            "last_status": p.last_status,
            "is_task": p.is_task,
            "created_by": p.created_by,
            "started_at": p.started_at.isoformat() if p.started_at else None,
            "last_modified_at": p.last_modified_at.isoformat() if p.last_modified_at else None,
            "last_step": p.last_step,
        }
        for p in processes
    ]


def fetch_product_block_export_data(entity_ids: list[str]) -> list[dict]:
    """Fetch product block definition data for export.

    Args:
        entity_ids: List of product block IDs as strings

    Returns:
        List of flattened product block dictionaries with fields:
        product_block_id, name, description, tag, status, created_at, end_date,
        resource_types (comma-separated), in_use_by (comma-separated)
    """
    stmt = (
        select(ProductBlockTable)
        .options(
            selectinload(ProductBlockTable.resource_types),
            selectinload(ProductBlockTable.in_use_by_block_relations).selectinload(
                ProductBlockRelationTable.in_use_by
            ),
        )
        .filter(ProductBlockTable.product_block_id.in_([UUID(pbid) for pbid in entity_ids]))
    )
    product_blocks = db.session.scalars(stmt).all()

    return [
        {
            "product_block_id": str(pb.product_block_id),
            "name": pb.name,
            "description": pb.description,
            "tag": pb.tag,
            "status": pb.status,
            "created_at": pb.created_at.isoformat() if pb.created_at else None,
            "end_date": pb.end_date.isoformat() if pb.end_date else None,
            "resource_types": ", ".join(rt.resource_type for rt in pb.resource_types),
            "in_use_by": ", ".join(b.name for b in pb.in_use_by),
        }
        for pb in product_blocks
    ]


def fetch_resource_type_export_data(entity_ids: list[str]) -> list[dict]:
    """Fetch resource type definition data for export.

    Args:
        entity_ids: List of resource type IDs as strings

    Returns:
        List of flattened resource type dictionaries with fields:
        resource_type_id, resource_type, description, product_blocks (comma-separated)
    """
    stmt = (
        select(ResourceTypeTable)
        .options(selectinload(ResourceTypeTable.product_blocks))
        .filter(ResourceTypeTable.resource_type_id.in_([UUID(rtid) for rtid in entity_ids]))
    )
    resource_types = db.session.scalars(stmt).all()

    return [
        {
            "resource_type_id": str(rt.resource_type_id),
            "resource_type": rt.resource_type,
            "description": rt.description,
            "product_blocks": ", ".join(pb.name for pb in rt.product_blocks),
        }
        for rt in resource_types
    ]


def fetch_export_data(entity_type: EntityType, entity_ids: list[str]) -> list[dict]:
    """Fetch export data for any entity type.

    Args:
        entity_type: The type of entities to fetch
        entity_ids: List of entity IDs/names as strings

    Returns:
        List of flattened entity dictionaries ready for CSV export

    Raises:
        ValueError: If entity_type is not supported
    """
    match entity_type:
        case EntityType.SUBSCRIPTION:
            return fetch_subscription_export_data(entity_ids)
        case EntityType.WORKFLOW:
            return fetch_workflow_export_data(entity_ids)
        case EntityType.PRODUCT:
            return fetch_product_export_data(entity_ids)
        case EntityType.PROCESS:
            return fetch_process_export_data(entity_ids)
        case EntityType.METADATA_PRODUCT_BLOCK:
            return fetch_product_block_export_data(entity_ids)
        case EntityType.METADATA_RESOURCE_TYPE:
            return fetch_resource_type_export_data(entity_ids)
        case _:
            raise ValueError(f"Unsupported entity type: {entity_type}")
