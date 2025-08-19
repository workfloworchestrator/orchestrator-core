from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, cast

import structlog
from sqlalchemy.inspection import inspect

from orchestrator.db import ProcessTable, ProductTable, SubscriptionTable, WorkflowTable
from orchestrator.domain import (
    SUBSCRIPTION_MODEL_REGISTRY,
    SubscriptionModel,
)
from orchestrator.domain.base import ProductBlockModel
from orchestrator.domain.lifecycle import (
    lookup_specialized_type,
)
from orchestrator.search.core.exceptions import ModelLoadError, ProductNotInRegistryError
from orchestrator.search.core.types import ExtractedField, FieldType, TypedValue
from orchestrator.types import SubscriptionLifecycle

logger = structlog.get_logger(__name__)


class BaseTraverser(ABC):
    """An abstract base class for traversing database models."""

    _LTREE_SEPARATOR = "."
    _MAX_DEPTH = 40

    @staticmethod
    def _traverse(data: Any, path: str = "", depth: int = 0, max_depth: int = _MAX_DEPTH) -> Iterable[ExtractedField]:
        """Recursive walk through dicts / lists; returns `(path, value)`."""
        if depth >= max_depth:
            logger.error("Max recursive depth reached while traversing: path=%s", path)
            return
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}{BaseTraverser._LTREE_SEPARATOR}{key}" if path else key
                yield from BaseTraverser._traverse(value, new_path, depth + 1, max_depth)

        elif isinstance(data, list):
            if len(data) == 1:
                yield from BaseTraverser._traverse(data[0], path, depth + 1, max_depth)
            else:
                for i, item in enumerate(data):
                    new_path = f"{path}{BaseTraverser._LTREE_SEPARATOR}{i}"
                    yield from BaseTraverser._traverse(item, new_path, depth + 1, max_depth)

        elif data is not None:
            yield ExtractedField.from_raw(path, data)

    @staticmethod
    def _dump_sqlalchemy_fields(entity: Any, exclude: set[str] | None = None) -> dict:
        """Serialize SQLAlchemy column attributes of an entity into a dictionary, with optional exclusions."""
        exclude = exclude or set()
        mapper = inspect(entity.__class__)
        if not mapper:
            return {}

        return {
            attr.key: getattr(entity, attr.key)
            for attr in mapper.column_attrs
            if hasattr(entity, attr.key) and attr.key not in exclude
        }

    @classmethod
    @abstractmethod
    def _dump(cls, entity: Any) -> dict:
        """Abstract method to convert a model instance to a dictionary."""
        ...

    @classmethod
    def get_fields(cls, entity: Any, pk_name: str, root_name: str) -> list[ExtractedField]:
        """Serializes a model instance and returns a list of (path, value) tuples."""
        try:
            data_dict = cls._dump(entity)
        except Exception as e:
            entity_id = getattr(entity, pk_name, "unknown")
            logger.error(f"Failed to serialize {entity.__class__.__name__}", id=str(entity_id), error=str(e))
            return []

        fields = cls._traverse(data_dict, path=root_name)
        return sorted(fields, key=lambda field: (field.path.count(cls._LTREE_SEPARATOR), field.path))


class SubscriptionTraverser(BaseTraverser):

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

    @classmethod
    def _dump(cls, sub: SubscriptionTable) -> dict:
        """Loads a Pydantic model, dumps it to a dict, and then transforms the keys."""
        model = cls._load_model(sub)
        if not model:
            return {}

        return model.model_dump(exclude_unset=False)


class ProductTraverser(BaseTraverser):
    """Product traverser dumps core product fields and a nested structure of product blocks."""

    @classmethod
    def _dump(cls, prod: ProductTable) -> dict[str, Any]:

        def dump_block_model(model: type[ProductBlockModel], seen: set[str]) -> dict[str, Any]:
            result = {}
            for attr, field in model.model_fields.items():
                field_type = field.annotation
                if isinstance(field_type, type) and issubclass(field_type, ProductBlockModel):
                    if attr not in seen:
                        seen.add(attr)
                        # Use TypedValue to indicate this is a block
                        result[attr] = TypedValue(attr, FieldType.BLOCK)
                else:
                    # Use TypedValue to indicate this is a resource type
                    result[attr] = TypedValue(attr, FieldType.RESOURCE_TYPE)
            return result

        base = cls._dump_sqlalchemy_fields(prod)

        # Get domain model for this product
        domain_model_cls = SUBSCRIPTION_MODEL_REGISTRY.get(prod.name)
        if not domain_model_cls:
            return base  # No model = skip block info

        try:
            lifecycle_model = cast(
                type[SubscriptionModel], lookup_specialized_type(domain_model_cls, SubscriptionLifecycle.INITIAL)
            )
        except Exception:
            lifecycle_model = domain_model_cls

        seen: set[str] = set()
        nested_blocks = {}

        for attr, field in lifecycle_model.model_fields.items():
            field_type = field.annotation
            if isinstance(field_type, type) and issubclass(field_type, ProductBlockModel):
                nested_blocks[attr] = dump_block_model(field_type, seen)

        if nested_blocks:
            base["product_blocks"] = nested_blocks

        return base


class ProcessTraverser(BaseTraverser):
    # We are explicitly excluding 'traceback' and 'steps'
    # to avoid overloading the index with too much data.
    _process_fields_to_exclude: set[str] = {
        "traceback",
    }

    @classmethod
    def _dump(cls, proc: ProcessTable) -> dict:
        """Serializes a ProcessTable instance into a dictionary, including key relationships."""

        base = cls._dump_sqlalchemy_fields(proc, exclude=cls._process_fields_to_exclude)

        if proc.workflow:
            base["workflow_name"] = proc.workflow.name

        if proc.subscriptions:
            base["subscriptions"] = [
                cls._dump_sqlalchemy_fields(sub) for sub in sorted(proc.subscriptions, key=lambda s: s.subscription_id)
            ]

        return base


class WorkflowTraverser(BaseTraverser):
    """Traverser for WorkflowTable entities."""

    @classmethod
    def _dump(cls, workflow: WorkflowTable) -> dict:
        """Serializes a WorkflowTable instance into a dictionary including all fields."""

        base = cls._dump_sqlalchemy_fields(workflow)

        if workflow.products:
            for product in sorted(workflow.products, key=lambda p: p.name):
                if product.tag:
                    product_key = product.tag.lower()

                    full_product_data = ProductTraverser._dump(product)

                    # Ignore nested dictionaries in the product data.
                    # We only want the top-level fields because thats what the search index expects.
                    product_reference = {
                        key: value for key, value in full_product_data.items() if not isinstance(value, dict)
                    }

                    base[product_key] = product_reference
                else:
                    logger.warning("Workflow has an associated product without a tag", product_name=product.name)

        return base
