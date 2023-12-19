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
from functools import partial
from typing import Annotated, Any, List, Optional, Sequence, Type
from uuid import UUID

import structlog
from pydantic import AfterValidator, Field

from orchestrator.services.products import get_product_by_id
from pydantic_forms.types import strEnum
from pydantic_forms.validators import (
    Accept,
    Choice,
    ContactPerson,
    ContactPersonName,
    DisplaySubscription,
    Divider,
    Label,
    ListOfOne,
    ListOfTwo,
    LongText,
    MigrationSummary,
    OrganisationId,
    Timestamp,
    choice_list,
    contact_person_list,
    migration_summary,
    timestamp,
    unique_conlist,
)

logger = structlog.get_logger(__name__)

__all__ = [
    "Accept",
    "Choice",
    "ContactPerson",
    "ContactPersonName",
    "DisplaySubscription",
    "Divider",
    "Label",
    "ListOfOne",
    "ListOfTwo",
    "LongText",
    "ProductIdError",
    "ProductId",
    "MigrationSummary",
    "OrganisationId",
    "Timestamp",
    "choice_list",
    "contact_person_list",
    "migration_summary",
    "product_id",
    "strEnum",
    "timestamp",
    "unique_conlist",
]


class ProductIdError(ValueError):
    code = "product_id"
    enum_values: Sequence[Any]  # Required kwarg

    def __init__(self, **ctx: Any) -> None:
        self.__dict__ = ctx

    def __str__(self) -> str:
        permitted = ", ".join(repr(v) for v in self.enum_values)
        return f"value is not a valid enumeration member; permitted: {permitted}"


def _validate_is_product(id_: UUID) -> UUID:
    if not get_product_by_id(id_, join_fixed_inputs=False):
        raise ValueError("Product not found")

    return id_


def _validate_in_products(product_ids: set[UUID], id_: UUID) -> UUID:
    if product_ids and id_ not in product_ids:
        raise ProductIdError(enum_values=list(map(str, product_ids)))

    return id_


ProductId = Annotated[UUID, AfterValidator(_validate_is_product), Field(json_schema_extra={"format": "productId"})]


def product_id(product_ids: Optional[List[UUID]] = None) -> Type[ProductId]:
    schema = {"uniforms": {"productIds": product_ids}} if product_ids else {}
    return Annotated[  # type: ignore[return-value]
        ProductId,
        AfterValidator(partial(_validate_in_products, set(product_ids or []))),
        Field(json_schema_extra={"format": "productId"} | schema),  # type: ignore[arg-type]
    ]


def remove_empty_items(v: list) -> list:
    """Remove Falsy values from list.

    Sees dicts with all Falsy values as Falsy.
    This is used to allow people to submit list fields which are "empty" but are not really empty like:
    `[{}, None, {name:"", email:""}]`

    Example:
        >>> remove_empty_items([{}, None, [], {"a":""}])
        []
    """
    if v:
        return list(filter(lambda i: bool(i) and (not isinstance(i, dict) or any(i.values())), v))
    return v
