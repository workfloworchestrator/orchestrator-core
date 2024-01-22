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


from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from orchestrator.db import ProductTable, db
from orchestrator.types import UUIDstr


def get_products(*, filters: list | None = None) -> list[ProductTable]:
    stmt = select(ProductTable)
    for clause in filters or []:
        stmt = stmt.where(clause)
    return list(db.session.scalars(stmt))


def get_product_by_id(product_id: UUID | UUIDstr, join_fixed_inputs: bool = True) -> ProductTable | None:
    """Get product by id.

    Args:
        product_id: ProductTable id uuid
        join_fixed_inputs: whether to join the fixed inputs in the same query or not

    Returns: ProductTable object

    """
    if not join_fixed_inputs:
        return db.session.get(ProductTable, product_id)

    return db.session.get(ProductTable, product_id, options=[joinedload(ProductTable.fixed_inputs)])


def get_product_by_name(name: str) -> ProductTable:
    stmt = select(ProductTable).options(joinedload(ProductTable.fixed_inputs)).where(ProductTable.name == name)
    return db.session.scalars(stmt).unique().one()


def get_types() -> list[str]:
    stmt = select(ProductTable.product_type).distinct()
    return list(db.session.scalars(stmt))


def get_tags() -> list[str]:
    stmt = select(ProductTable.tag).distinct()
    return list(db.session.scalars(stmt))
