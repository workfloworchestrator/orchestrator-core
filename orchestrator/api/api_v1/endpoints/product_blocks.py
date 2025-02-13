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

from fastapi.param_functions import Body
from fastapi.routing import APIRouter

from orchestrator.api.error_handling import raise_status
from orchestrator.db import db
from orchestrator.db.models import ProductBlockTable
from orchestrator.schemas.product_block import ProductBlockPatchSchema, ProductBlockSchema

router = APIRouter()


@router.get("/{product_block_id}", response_model=ProductBlockSchema)
def get_product_block_description(product_block_id: UUID) -> str:
    product_block = db.session.get(ProductBlockTable, product_block_id)
    if product_block is None:
        raise_status(HTTPStatus.NOT_FOUND)
    return product_block


@router.patch("/{product_block_id}", status_code=HTTPStatus.CREATED, response_model=ProductBlockSchema)
async def patch_product_block_by_id(
    product_block_id: UUID, data: ProductBlockPatchSchema = Body(...)
) -> ProductBlockTable:
    product_block = db.session.get(ProductBlockTable, product_block_id)
    if not product_block:
        raise_status(HTTPStatus.NOT_FOUND, f"Product_block id {product_block_id} not found")

    return await _patch_product_block_description(data, product_block)


async def _patch_product_block_description(
    data: ProductBlockPatchSchema,
    product_block: ProductBlockTable,
) -> ProductBlockTable:

    updated_properties = data.model_dump(exclude_unset=True)
    description = updated_properties.get("description", product_block.description)
    product_block.description = description
    db.session.commit()
    return product_block
