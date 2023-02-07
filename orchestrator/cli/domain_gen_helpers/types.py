from typing import Dict, Set, Type

from pydantic import BaseModel

from orchestrator.domain.base import ProductBlockModel, SubscriptionModel


class DomainModelChanges(BaseModel):
    create_products: Dict[str, Type[SubscriptionModel]] = {}
    delete_products: Set[str] = set()
    create_product_to_block_relations: Dict[str, Set[str]] = {}
    delete_product_to_block_relations: Dict[str, Set[str]] = {}
    create_product_blocks: Dict[str, Type[ProductBlockModel]] = {}
    delete_product_blocks: Set[str] = set()
    create_product_block_relations: Dict[str, Set[str]] = {}
    delete_product_block_relations: Dict[str, Set[str]] = {}
    create_product_fixed_inputs: Dict[str, Set[str]] = {}
    update_product_fixed_inputs: Dict[str, Dict[str, str]] = {}
    delete_product_fixed_inputs: Dict[str, Set[str]] = {}
    create_resource_types: Set[str] = set()
    rename_resource_types: Dict[str, str] = {}
    update_block_resource_types: Dict[str, Dict[str, str]] = {}
    delete_resource_types: Set[str] = set()
    create_resource_type_relations: Dict[str, Set[str]] = {}
    create_resource_type_instance_relations: Dict[str, Set[str]] = {}
    delete_resource_type_relations: Dict[str, Set[str]] = {}


class DuplicateException(Exception):
    pass


class ModelUpdates(BaseModel):
    fixed_inputs: Dict[str, Dict[str, str]] = {}
    resource_types: Dict[str, str] = {}
    block_resource_types: Dict[str, Dict[str, str]] = {}
