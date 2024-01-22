from pydantic import BaseModel

from orchestrator.domain.base import ProductBlockModel, SubscriptionModel


class DomainModelChanges(BaseModel):
    create_products: dict[str, type[SubscriptionModel]] = {}
    delete_products: set[str] = set()
    create_product_to_block_relations: dict[str, set[str]] = {}
    delete_product_to_block_relations: dict[str, set[str]] = {}
    create_product_blocks: dict[str, type[ProductBlockModel]] = {}
    delete_product_blocks: set[str] = set()
    create_product_block_relations: dict[str, set[str]] = {}
    delete_product_block_relations: dict[str, set[str]] = {}
    create_product_fixed_inputs: dict[str, set[str]] = {}
    update_product_fixed_inputs: dict[str, dict[str, str]] = {}
    delete_product_fixed_inputs: dict[str, set[str]] = {}
    create_resource_types: set[str] = set()
    rename_resource_types: dict[str, str] = {}
    update_block_resource_types: dict[str, dict[str, str]] = {}
    delete_resource_types: set[str] = set()
    create_resource_type_relations: dict[str, set[str]] = {}
    create_resource_type_instance_relations: dict[str, set[str]] = {}
    delete_resource_type_relations: dict[str, set[str]] = {}


class DuplicateError(Exception):
    pass


class ModelUpdates(BaseModel):
    fixed_inputs: dict[str, dict[str, str]] = {}
    resource_types: dict[str, str] = {}
    block_resource_types: dict[str, dict[str, str]] = {}
