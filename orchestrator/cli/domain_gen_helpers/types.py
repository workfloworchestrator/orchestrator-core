from typing import Dict, List, Set, Type

from pydantic import BaseModel

from orchestrator.domain.base import ProductBlockModel, SubscriptionModel


class DomainModelChanges(BaseModel):
    create_products: Dict[str, Type[SubscriptionModel]] = {}
    delete_products: List[str] = []
    create_product_to_block_relations: Dict[str, Set[str]] = {}
    delete_product_to_block_relations: Dict[str, Set[str]] = {}
    create_product_blocks: Dict[str, Type[ProductBlockModel]] = {}
    delete_product_blocks: List[str] = []
    create_product_block_relations: Dict[str, Set[str]] = {}
    delete_product_block_relations: Dict[str, Set[str]] = {}
    create_product_fixed_inputs: Dict[str, Set[str]] = {}
    update_product_fixed_inputs: Dict[str, Dict[str, str]] = {}
    delete_product_fixed_inputs: Dict[str, Set[str]] = {}
    create_resource_types: List[str] = []
    update_resource_types: Dict[str, str] = {}
    delete_resource_types: List[str] = []
    create_resource_type_relations: Dict[str, Set[str]] = {}
    delete_resource_type_relations: Dict[str, Set[str]] = {}


class DuplicateException(Exception):
    pass
