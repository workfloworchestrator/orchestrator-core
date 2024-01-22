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
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from orchestrator.api.error_handling import raise_status
from orchestrator.api.models import delete, save, update
from orchestrator.db import ProductBlockTable, ProductTable, SubscriptionTable, db
from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.schemas import ProductCRUDSchema, ProductSchema
from orchestrator.services.products import get_tags, get_types

router = APIRouter()


@router.get("/", response_model=list[ProductSchema])
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


@router.get("/{product_id}", response_model=ProductSchema)
def product_by_id(product_id: UUID) -> ProductTable:
    stmt = (
        select(ProductTable)
        .options(
            joinedload(ProductTable.fixed_inputs),
            joinedload(ProductTable.product_blocks),
            joinedload(ProductTable.workflows),
        )
        .filter(ProductTable.product_id == product_id)
    )
    product = db.session.scalars(stmt).unique().one_or_none()
    if not product:
        raise_status(HTTPStatus.NOT_FOUND, f"Product id {product_id} not found")
    return product


@router.post("/", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def save_product(data: ProductCRUDSchema = Body(...)) -> None:
    return save(ProductTable, data)


@router.put("/", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def update_product(data: ProductCRUDSchema = Body(...)) -> None:
    return update(ProductTable, data)


@router.delete("/{product_id}", response_model=None, status_code=HTTPStatus.NO_CONTENT)
def delete_product(product_id: UUID) -> None:
    subscriptions_stmt = select(SubscriptionTable).filter(SubscriptionTable.product_id == product_id)
    subscriptions = db.session.scalars(subscriptions_stmt).all()
    if len(subscriptions) > 0:
        error_subscriptions = ", ".join(map(lambda sub: sub.description, subscriptions))
        raise_status(HTTPStatus.BAD_REQUEST, f"Product {product_id} is used in Subscriptions: {error_subscriptions}")
    return delete(ProductTable, product_id)


@router.get("/tags/all", response_model=list[str])
def tags() -> list[str]:
    return get_tags()


@router.get("/types/all", response_model=list[str])
def types() -> list[str]:
    return get_types()


@router.get("/statuses/all", response_model=list[ProductLifecycle])
def statuses() -> list[ProductLifecycle]:
    return ProductLifecycle.values()
