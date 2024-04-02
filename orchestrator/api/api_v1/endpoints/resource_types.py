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
from uuid import UUID

from fastapi.params import Body, Depends
from fastapi.routing import APIRouter
from sqlalchemy import select

from orchestrator.api.error_handling import raise_status
from orchestrator.api.models import delete, save, update
from orchestrator.db import ProductBlockTable, ResourceTypeTable, db
from orchestrator.schemas import ResourceTypeBaseSchema, ResourceTypeSchema
from orchestrator.services.resource_types import get_resource_types
from orchestrator.utils.deprecation_logger import deprecated_endpoint

router = APIRouter()


@router.get(
    "/",
    response_model=list[ResourceTypeSchema],
    deprecated=True,
    description="This endpoint is deprecated and will be removed in a future release. Please use the GraphQL query",
    dependencies=[Depends(deprecated_endpoint)],
)
def fetch() -> list[ResourceTypeTable]:
    return get_resource_types()


@router.get(
    "/{resource_type_id}",
    response_model=ResourceTypeSchema,
    deprecated=True,
    description="This endpoint is deprecated and will be removed in a future release. Please use the GraphQL query",
    dependencies=[Depends(deprecated_endpoint)],
)
def resource_type_by_id(resource_type_id: UUID) -> ResourceTypeTable:
    resource_type_stmt = select(ResourceTypeTable).filter_by(resource_type_id=resource_type_id)
    resource_type = db.session.scalars(resource_type_stmt).first()
    if not resource_type:
        raise_status(HTTPStatus.NOT_FOUND, f"Resource type {resource_type_id} not found")
    return resource_type


@router.post(
    "/",
    response_model=None,
    status_code=HTTPStatus.NO_CONTENT,
    deprecated=True,
    description="This endpoint is deprecated and will be removed in a future release. Please use the GraphQL query",
    dependencies=[Depends(deprecated_endpoint)],
)
def save_resource_type(data: ResourceTypeBaseSchema = Body(...)) -> None:  # type: ignore
    return save(ResourceTypeTable, data)


@router.put(
    "/",
    response_model=None,
    status_code=HTTPStatus.NO_CONTENT,
    deprecated=True,
    description="This endpoint is deprecated and will be removed in a future release. Please use the GraphQL query",
    dependencies=[Depends(deprecated_endpoint)],
)
def update_resource_type(data: ResourceTypeSchema = Body(...)) -> None:  # type: ignore
    return update(ResourceTypeTable, data)


@router.delete("/{resource_type_id}", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def delete_resource_type(resource_type_id: UUID) -> None:
    product_blocks_stmt = select(ProductBlockTable).filter(
        ProductBlockTable.resource_types.any(ResourceTypeTable.resource_type_id == str(resource_type_id))
    )
    product_blocks = db.session.scalars(product_blocks_stmt).all()
    if len(product_blocks) > 0:
        error_products_block = ", ".join(map(lambda pb: pb.name, product_blocks))
        raise_status(
            HTTPStatus.BAD_REQUEST, f"ResourceType {resource_type_id} is used in ProductBlocks: {error_products_block}"
        )
    return delete(ResourceTypeTable, resource_type_id)
