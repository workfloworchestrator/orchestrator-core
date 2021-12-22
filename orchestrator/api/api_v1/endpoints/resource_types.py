# Copyright 2019-2020 SURF.
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

from http import HTTPStatus
from typing import List
from uuid import UUID

from fastapi.param_functions import Body
from fastapi.routing import APIRouter

from orchestrator.api.error_handling import raise_status
from orchestrator.api.models import delete, save, update
from orchestrator.db import ProductBlockTable, ResourceTypeTable
from orchestrator.schemas import ResourceTypeBaseSchema, ResourceTypeSchema, ResourceTypeSchemaORM

router = APIRouter()


@router.get("/", response_model=List[ResourceTypeSchemaORM])
def fetch() -> List[ResourceTypeTable]:
    return ResourceTypeTable.query.all()


@router.get("/{resource_type_id}", response_model=ResourceTypeSchemaORM)
def resource_type_by_id(resource_type_id: UUID) -> ResourceTypeTable:
    resource_type = ResourceTypeTable.query.filter_by(resource_type_id=resource_type_id).first()
    if not resource_type:
        raise_status(HTTPStatus.NOT_FOUND, f"Resource type {resource_type_id} not found")
    return resource_type


@router.post("/", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def save_resource_type(data: ResourceTypeBaseSchema = Body(...)) -> None:
    return save(ResourceTypeTable, data)


@router.put("/", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def update_resource_type(data: ResourceTypeSchema = Body(...)) -> None:
    return update(ResourceTypeTable, data)


@router.delete("/{resource_type_id}", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def delete_resource_type(resource_type_id: UUID) -> None:
    product_blocks = ProductBlockTable.query.filter(
        ProductBlockTable.resource_types.any(ResourceTypeTable.resource_type_id == str(resource_type_id))
    ).all()
    if len(product_blocks) > 0:
        error_products_block = ", ".join(map(lambda pb: pb.name, product_blocks))
        raise_status(
            HTTPStatus.BAD_REQUEST, f"ResourceType {resource_type_id} is used in ProductBlocks: {error_products_block}"
        )
    return delete(ResourceTypeTable, resource_type_id)
