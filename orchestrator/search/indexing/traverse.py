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

import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from enum import Enum
from typing import Any, cast, get_args
from uuid import uuid4

import structlog

from orchestrator.db import ProcessTable, ProductTable, SubscriptionTable, WorkflowTable
from orchestrator.domain import (
    SUBSCRIPTION_MODEL_REGISTRY,
    SubscriptionModel,
)
from orchestrator.domain.base import ProductBlockModel, ProductModel
from orchestrator.domain.lifecycle import (
    lookup_specialized_type,
)
from orchestrator.schemas.process import ProcessSchema
from orchestrator.schemas.workflow import WorkflowSchema
from orchestrator.search.core.exceptions import ModelLoadError, ProductNotInRegistryError
from orchestrator.search.core.types import LTREE_SEPARATOR, ExtractedField, FieldType
from orchestrator.types import SubscriptionLifecycle

logger = structlog.get_logger(__name__)

DatabaseEntity = SubscriptionTable | ProductTable | ProcessTable | WorkflowTable


class BaseTraverser(ABC):
    """Base class for traversing database models and extracting searchable fields."""

    _MAX_DEPTH = 40

    @classmethod
    def get_fields(cls, entity: DatabaseEntity, pk_name: str, root_name: str) -> list[ExtractedField]:
        """Main entry point for extracting fields from an entity. Default implementation delegates to _load_model."""
        try:
            model = cls._load_model(entity)
            if model is None:
                return []
            return sorted(cls.traverse(model, root_name), key=lambda f: f.path)

        except (ProductNotInRegistryError, ModelLoadError) as e:
            entity_id = getattr(entity, pk_name, "unknown")
            logger.error(f"Failed to extract fields from {entity.__class__.__name__}", id=str(entity_id), error=str(e))
            return []

    @classmethod
    def traverse(cls, instance: Any, path: str = "") -> Iterable[ExtractedField]:
        """Walks the fields of a Pydantic model, dispatching each to a field handler."""
        model_class = type(instance)

        # Handle both standard and computed fields from the Pydantic model
        all_fields = model_class.model_fields.copy()
        all_fields.update(getattr(model_class, "__pydantic_computed_fields__", {}))

        for name, field in all_fields.items():
            try:
                value = getattr(instance, name, None)
            except Exception as e:
                logger.error(f"Failed to access field '{name}' on {model_class.__name__}", error=str(e))
                continue
            new_path = f"{path}{LTREE_SEPARATOR}{name}" if path else name
            annotation = field.annotation if hasattr(field, "annotation") else field.return_type
            yield from cls._yield_fields_for_value(value, new_path, annotation)

    @classmethod
    def _yield_fields_for_value(cls, value: Any, path: str, annotation: Any) -> Iterable[ExtractedField]:
        """Yields fields for a given value based on its type (model, list, or scalar)."""
        if value is None:
            return

        # If the value is a list, pass it to the list traverser
        if isinstance(value, list):
            if element_annotation := get_args(annotation):
                yield from cls._traverse_list(value, path, element_annotation[0])
            return

        # If the value is another Pydantic model, recurse into it
        if hasattr(type(value), "model_fields"):
            yield from cls.traverse(value, path)
            return

        ftype = FieldType.from_type_hint(annotation)

        if isinstance(value, Enum):
            yield ExtractedField(path, str(value.value), ftype)
        else:
            yield ExtractedField(path, str(value), ftype)

    @classmethod
    def _traverse_list(cls, items: list[Any], path: str, element_annotation: Any) -> Iterable[ExtractedField]:
        """Recursively traverses items in a list."""
        for i, item in enumerate(items):
            item_path = f"{path}.{i}"
            yield from cls._yield_fields_for_value(item, item_path, element_annotation)

    @classmethod
    def _load_model_with_schema(cls, entity: Any, schema_class: type[Any], pk_name: str) -> Any:
        """Generic helper for loading models using Pydantic schema validation."""
        try:
            return schema_class.model_validate(entity)
        except Exception as e:
            entity_id = getattr(entity, pk_name, "unknown")
            raise ModelLoadError(f"Failed to load {schema_class.__name__} for {pk_name} '{entity_id}'") from e

    @classmethod
    @abstractmethod
    def _load_model(cls, entity: Any) -> Any: ...


class SubscriptionTraverser(BaseTraverser):
    """Traverser for subscription entities using full Pydantic model extraction."""

    @classmethod
    def _load_model(cls, sub: SubscriptionTable) -> SubscriptionModel | None:
        base_model_cls = SUBSCRIPTION_MODEL_REGISTRY.get(sub.product.name)
        if not base_model_cls:
            raise ProductNotInRegistryError(f"Product '{sub.product.name}' not in registry.")

        specialized_model_cls = cast(type[SubscriptionModel], lookup_specialized_type(base_model_cls, sub.status))

        try:
            return specialized_model_cls.from_subscription(sub.subscription_id)
        except Exception as e:
            raise ModelLoadError(f"Failed to load model for subscription_id '{sub.subscription_id}'") from e


class ProductTraverser(BaseTraverser):
    """Traverser for product entities using a template SubscriptionModel instance."""

    @classmethod
    def _sanitize_for_ltree(cls, name: str) -> str:
        """Sanitizes a string to be a valid ltree path label."""
        # Convert to lowercase
        sanitized = name.lower()

        # Replace all non-alphanumeric (and non-underscore) characters with an underscore
        sanitized = re.sub(r"[^a-z0-9_]", "_", sanitized)

        # Collapse multiple underscores into a single one
        sanitized = re.sub(r"__+", "_", sanitized)

        # Remove leading or trailing underscores
        sanitized = sanitized.strip("_")

        # Handle cases where the name was only invalid characters
        if not sanitized:
            return "unnamed_product"

        return sanitized

    @classmethod
    def get_fields(cls, entity: ProductTable, pk_name: str, root_name: str) -> list[ExtractedField]:  # type: ignore[override]
        """Extracts fields by creating a template SubscriptionModel instance for the product.

        Extracts product metadata and block schema structure.
        """
        try:
            model = cls._load_model(entity)

            if not model:
                return []

            fields: list[ExtractedField] = []

            product_fields = cls.traverse(model.product, root_name)
            fields.extend(product_fields)

            product_name = cls._sanitize_for_ltree(model.product.name)

            product_block_root = f"{root_name}.{product_name}.product_block"

            # Extract product block schema structure
            model_class = type(model)
            product_block_fields = getattr(model_class, "_product_block_fields_", {})

            for field_name in product_block_fields:
                block_value = getattr(model, field_name, None)
                if block_value is not None:
                    block_path = f"{product_block_root}.{field_name}"
                    schema_fields = cls._extract_block_schema(block_value, block_path)
                    fields.extend(schema_fields)

            return sorted(fields, key=lambda f: f.path)

        except (ProductNotInRegistryError, ModelLoadError) as e:
            entity_id = getattr(entity, pk_name, "unknown")
            logger.error(f"Failed to extract fields from {entity.__class__.__name__}", id=str(entity_id), error=str(e))
            return []

    @classmethod
    def _extract_block_schema(cls, block_instance: ProductBlockModel, block_path: str) -> list[ExtractedField]:
        """Extract schema information from a block instance, returning field names as RESOURCE_TYPE."""
        fields = []

        # Add the block itself as a BLOCK type
        block_name = block_path.split(LTREE_SEPARATOR)[-1]
        fields.append(ExtractedField(path=block_path, value=block_name, value_type=FieldType.BLOCK))

        # Extract all field names from the block as RESOURCE_TYPE
        if hasattr(type(block_instance), "model_fields"):
            all_fields = type(block_instance).model_fields
            computed_fields = getattr(block_instance, "__pydantic_computed_fields__", None)
            if computed_fields:
                all_fields.update(computed_fields)

            for field_name in all_fields:
                field_value = getattr(block_instance, field_name, None)
                field_path = f"{block_path}.{field_name}"

                # If it's a nested block, recurse
                if field_value is not None and isinstance(field_value, ProductBlockModel):
                    nested_fields = cls._extract_block_schema(field_value, field_path)
                    fields.extend(nested_fields)
                elif field_value is not None and isinstance(field_value, list):
                    # Handle list of blocks
                    if field_value and isinstance(field_value[0], ProductBlockModel):
                        # For lists, we still add the list field as a resource type
                        fields.append(
                            ExtractedField(path=field_path, value=field_name, value_type=FieldType.RESOURCE_TYPE)
                        )
                        # And potentially traverse the first item for schema
                        first_item_path = f"{field_path}{LTREE_SEPARATOR}0"
                        nested_fields = cls._extract_block_schema(field_value[0], first_item_path)
                        fields.extend(nested_fields)
                    else:
                        fields.append(
                            ExtractedField(path=field_path, value=field_name, value_type=FieldType.RESOURCE_TYPE)
                        )
                else:
                    # Regular fields are resource types
                    fields.append(ExtractedField(path=field_path, value=field_name, value_type=FieldType.RESOURCE_TYPE))

        return fields

    @classmethod
    def _load_model(cls, product: ProductTable) -> SubscriptionModel | None:
        """Creates a template instance of a SubscriptionModel for a given product.

        This allows us to traverse the product's defined block structure, even
        without a real subscription instance in the database.
        """
        # Find the SubscriptionModel class associated with this product's name.
        domain_model_cls = SUBSCRIPTION_MODEL_REGISTRY.get(product.name)
        if not domain_model_cls:
            raise ProductNotInRegistryError(f"Product '{product.name}' not in registry.")

        # Get the initial lifecycle version of that class, as it represents the base structure.
        try:
            subscription_model_cls = cast(
                type[SubscriptionModel], lookup_specialized_type(domain_model_cls, SubscriptionLifecycle.INITIAL)
            )
        except Exception:
            subscription_model_cls = domain_model_cls

        try:
            product_model = ProductModel(
                product_id=product.product_id,
                name=product.name,
                description=product.description,
                product_type=product.product_type,
                tag=product.tag,
                status=product.status,
            )

            # Generate a fake subscription ID for the template
            subscription_id = uuid4()

            # Get fixed inputs for the product
            fixed_inputs = {fi.name: fi.value for fi in product.fixed_inputs}

            # Initialize product blocks
            instances = subscription_model_cls._init_instances(subscription_id)

            return subscription_model_cls(
                product=product_model,
                customer_id="traverser_template",
                subscription_id=subscription_id,
                description="Template for schema traversal",
                status=SubscriptionLifecycle.INITIAL,
                insync=False,
                start_date=None,
                end_date=None,
                note=None,
                version=1,
                **fixed_inputs,
                **instances,
            )
        except Exception:
            logger.exception("Failed to instantiate template model for product", product_name=product.name)
            return None


class ProcessTraverser(BaseTraverser):
    """Traverser for process entities using ProcessSchema model.

    Note: Currently extracts only top-level process fields. Could be extended to include:
    - Related subscriptions (entity.subscriptions)
    - Related workflow information beyond workflow_name
    """

    @classmethod
    def _load_model(cls, process: ProcessTable) -> ProcessSchema:
        """Load process model using ProcessSchema."""
        return cls._load_model_with_schema(process, ProcessSchema, "process_id")


class WorkflowTraverser(BaseTraverser):
    """Traverser for workflow entities using WorkflowSchema model.

    Note: Currently extracts only top-level workflow fields. Could be extended to include:
    - Related products (entity.products) - each with their own block structures
    - Related processes (entity.processes) - each with their own process data
    """

    @classmethod
    def _load_model(cls, workflow: WorkflowTable) -> WorkflowSchema:
        """Load workflow model using WorkflowSchema."""
        return cls._load_model_with_schema(workflow, WorkflowSchema, "workflow_id")
