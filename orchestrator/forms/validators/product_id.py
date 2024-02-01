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
from collections.abc import Sequence
from functools import partial
from typing import Annotated, Any
from uuid import UUID

import structlog
from pydantic import AfterValidator, Field

from orchestrator.services.products import get_product_by_id

logger = structlog.get_logger(__name__)


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


def product_id(product_ids: list[UUID] | None = None) -> type[ProductId]:
    schema = {"uniforms": {"productIds": product_ids}} if product_ids else {}
    return Annotated[  # type: ignore[return-value]
        ProductId,
        AfterValidator(partial(_validate_in_products, set(product_ids or []))),
        Field(json_schema_extra={"format": "productId"} | schema),  # type: ignore[arg-type]
    ]
