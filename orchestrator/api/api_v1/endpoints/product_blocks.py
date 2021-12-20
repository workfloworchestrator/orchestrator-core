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
from sqlalchemy.orm import joinedload

from orchestrator.api.error_handling import raise_status
from orchestrator.api.models import delete, save, update
from orchestrator.db import ProductBlockTable, ProductTable
from orchestrator.schemas import ProductBlockBaseSchema
from orchestrator.schemas import ProductBlockEnrichedSchema as ProductBlockSchema

router = APIRouter()


@router.get("/", response_model=List[ProductBlockSchema])
def fetch() -> List[ProductBlockTable]:
    return ProductBlockTable.query.options(joinedload("resource_types")).all()


@router.get("/{product_block_id}", response_model=ProductBlockSchema)
def product_block_by_id(product_block_id: UUID) -> ProductBlockTable:
    product_block = (
        ProductBlockTable.query.options(joinedload("resource_types"))
        .filter_by(product_block_id=product_block_id)
        .first()
    )
    if not product_block:
        raise_status(HTTPStatus.NOT_FOUND, f"Product block id {product_block_id} not found")
    return product_block


@router.post("/", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def save_product_block(data: ProductBlockBaseSchema = Body(...)) -> None:
    return save(ProductBlockTable, data)


@router.put("/", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def update_product_block(data: ProductBlockBaseSchema = Body(...)) -> None:
    return update(ProductBlockTable, data)


@router.delete("/{product_block_id}", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def delete_product_block(product_block_id: UUID) -> None:
    products = ProductTable.query.filter(
        ProductTable.product_blocks.any(ProductBlockTable.product_block_id == product_block_id)
    ).all()
    if len(products) > 0:
        error_products = ", ".join(map(lambda product: product.name, products))
        raise_status(HTTPStatus.BAD_REQUEST, f"ProductBlock {product_block_id} is used in Products: {error_products}")

    return delete(ProductBlockTable, product_block_id)
