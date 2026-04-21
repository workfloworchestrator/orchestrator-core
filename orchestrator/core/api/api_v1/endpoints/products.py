# Copyright 2019-2026 SURF, ESnet, GÉANT.
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
from typing import Any, AsyncGenerator
from uuid import UUID

from fastapi.param_functions import Body, Depends
from fastapi.routing import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from orchestrator.core.api.error_handling import raise_status
from orchestrator.core.db import ProductBlockTable, ProductTable, SubscriptionTable, db
from orchestrator.core.domain.lifecycle import ProductLifecycle
from orchestrator.core.schemas import ProductSchema
from orchestrator.core.schemas.product import ProductPatchSchema
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.indexing import run_indexing_for_entity
from orchestrator.core.types import SubscriptionLifecycle

router = APIRouter()


@router.get(
    "/",
    response_model=list[ProductSchema],
)
def fetch(tag: str | None = None, product_type: str | None = None) -> list[ProductSchema]:
    stmt = select(ProductTable).options(
        selectinload(ProductTable.workflows),
        selectinload(ProductTable.fixed_inputs),
        selectinload(ProductTable.product_blocks).selectinload(ProductBlockTable.resource_types),
    )
    if tag:
        stmt = stmt.filter(ProductTable.__dict__["tag"] == tag)
    if product_type:
        stmt = stmt.filter(ProductTable.__dict__["product_type"] == product_type)

    return list(db.session.scalars(stmt))


@router.get(
    "/{product_id}",
    response_model=ProductSchema,
)
def product_by_id(product_id: UUID) -> ProductTable:
    product = _product_by_id(product_id)
    if not product:
        raise_status(HTTPStatus.NOT_FOUND, f"Product id {product_id} not found")
    return product


def _product_by_id(product_id: UUID) -> ProductTable | None:
    stmt = (
        select(ProductTable)
        .options(
            joinedload(ProductTable.fixed_inputs),
            joinedload(ProductTable.product_blocks),
            joinedload(ProductTable.workflows),
        )
        .filter(ProductTable.product_id == product_id)
    )
    return db.session.scalars(stmt).unique().one_or_none()


async def _index_products(product_id: UUID) -> AsyncGenerator[None, Any]:
    yield
    run_indexing_for_entity(EntityType.PRODUCT, str(product_id))


@router.patch(
    "/{product_id}",
    status_code=HTTPStatus.CREATED,
    response_model=ProductSchema,
    dependencies=[Depends(_index_products)],
)
async def patch_product_by_id(product_id: UUID, data: ProductPatchSchema = Body(...)) -> ProductTable:
    product = _product_by_id(product_id)
    if not product:
        raise_status(HTTPStatus.NOT_FOUND, f"Product id {product_id} not found")

    return await _patch_product(data, product)


async def _patch_product(
    data: ProductPatchSchema,
    product: ProductTable,
) -> ProductTable:

    updated_properties = data.model_dump(exclude_unset=True)

    # Update description if provided
    description = updated_properties.get("description", product.description)
    product.description = description

    # Update status if provided
    if "status" in updated_properties:
        new_status = updated_properties["status"]

        # Validate: cannot set END_OF_LIFE if non-terminated subscriptions exist
        if new_status == ProductLifecycle.END_OF_LIFE:
            non_terminated_count = db.session.scalar(
                select(func.count(SubscriptionTable.subscription_id)).where(
                    SubscriptionTable.product_id == product.product_id,
                    SubscriptionTable.status != SubscriptionLifecycle.TERMINATED,
                )
            )
            if non_terminated_count and non_terminated_count > 0:
                raise_status(
                    HTTPStatus.BAD_REQUEST,
                    f"Cannot set product to 'end of life': "
                    f"{non_terminated_count} subscription(s) are not in terminated state",
                )

        product.status = new_status

    db.session.commit()
    return product
