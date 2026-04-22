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

from pydantic import BaseModel
from typing_extensions import TypedDict

from orchestrator.core.domain.base import ProductBlockModel, SubscriptionModel


class BlockRelationDict(TypedDict):
    name: str
    attribute_name: str


class DomainModelChanges(BaseModel):
    create_products: dict[str, type[SubscriptionModel]] = {}
    delete_products: set[str] = set()
    create_product_to_block_relations: dict[str, set[str]] = {}
    delete_product_to_block_relations: dict[str, set[str]] = {}
    create_product_blocks: dict[str, type[ProductBlockModel]] = {}
    delete_product_blocks: set[str] = set()
    create_product_block_relations: dict[str, list[BlockRelationDict]] = {}
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
