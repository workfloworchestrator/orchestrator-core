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
from typing import List, Optional
from uuid import UUID

from fastapi.param_functions import Body
from fastapi.routing import APIRouter
from sqlalchemy.orm import joinedload, selectinload

from orchestrator.api.error_handling import raise_status
from orchestrator.api.models import delete, save, update
from orchestrator.db import ProductTable, SubscriptionTable
from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.schemas import ProductCRUDSchema, ProductSchema
from orchestrator.services.products import get_tags, get_types

router = APIRouter()


@router.get("/", response_model=List[ProductSchema])
def fetch(tag: Optional[str] = None, product_type: Optional[str] = None) -> List[ProductSchema]:
    query = ProductTable.query.options(
        selectinload("workflows"), selectinload("fixed_inputs"), selectinload("product_blocks")
    )
    if tag:
        query = query.filter(ProductTable.__dict__["tag"] == tag)
    if product_type:
        query = query.filter(ProductTable.__dict__["product_type"] == product_type)

    return query.all()


@router.get("/{product_id}", response_model=ProductSchema)
def product_by_id(product_id: UUID) -> ProductTable:
    product = (
        ProductTable.query.options(joinedload("fixed_inputs"), joinedload("product_blocks"), joinedload("workflows"))
        .filter_by(product_id=product_id)
        .first()
    )
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
    subscriptions = SubscriptionTable.query.filter(SubscriptionTable.product_id == product_id).all()
    if len(subscriptions) > 0:
        error_subscriptions = ", ".join(map(lambda sub: sub.description, subscriptions))
        raise_status(HTTPStatus.BAD_REQUEST, f"Product {product_id} is used in Subscriptions: {error_subscriptions}")
    return delete(ProductTable, product_id)


@router.get("/tags/all", response_model=List[str])
def tags() -> List[str]:
    return get_tags()


@router.get("/types/all", response_model=List[str])
def types() -> List[str]:
    return get_types()


@router.get("/statuses/all", response_model=List[ProductLifecycle])
def statuses() -> List[ProductLifecycle]:
    return ProductLifecycle.values()
