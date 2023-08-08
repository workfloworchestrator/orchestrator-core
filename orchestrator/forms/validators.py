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

from types import new_class
from typing import Any, Dict, Generator, List, Optional, Sequence, Type
from uuid import UUID

import structlog
from pydantic.errors import EnumMemberError
from pydantic.validators import uuid_validator

from orchestrator.services import products
from pydantic_forms.types import strEnum
from pydantic_forms.validators import (  # noqa: F401
    Accept,
    Choice,
    ChoiceList,
    ContactPerson,
    ContactPersonList,
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
    UniqueConstrainedList,
    choice_list,
    contact_person_list,
    migration_summary,
    remove_empty_items,
    timestamp,
    unique_conlist,
)

logger = structlog.get_logger(__name__)

__all__ = [
    "Accept",
    "Choice",
    "ChoiceList",
    "ContactPerson",
    "ContactPersonName",
    "ContactPersonList",
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
    "UniqueConstrainedList",
    "choice_list",
    "contact_person_list",
    "migration_summary",
    "product_id",
    "remove_empty_items",
    "strEnum",
    "timestamp",
    "unique_conlist",
]


class ProductIdError(EnumMemberError):
    code = "product_id"
    enum_values: Sequence[Any]  # Required kwarg

    def __str__(self) -> str:
        permitted = ", ".join(repr(v) for v in self.enum_values)
        return f"value is not a valid enumeration member; permitted: {permitted}"


class ProductId(UUID):
    products: Optional[List[UUID]] = None

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        kwargs = {"uniforms": {"productIds": cls.products}} if cls.products else {}
        field_schema.update(format="productId", **kwargs)

    @classmethod
    def __get_validators__(cls) -> Generator:
        yield uuid_validator
        yield cls.is_product
        if cls.products:
            yield cls.in_products

    @classmethod
    def is_product(cls, v: UUID) -> UUID:
        product = products.get_product_by_id(v)
        if product is None:
            raise ValueError("Product not found")

        return v

    @classmethod
    def in_products(cls, v: UUID) -> UUID:
        if cls.products and v not in cls.products:
            raise ProductIdError(enum_values=list(map(str, cls.products)))

        return v


def product_id(products: Optional[List[UUID]] = None) -> Type[ProductId]:
    namespace = {"products": products}
    return new_class("ProductIdSpecific", (ProductId,), {}, lambda ns: ns.update(namespace))
