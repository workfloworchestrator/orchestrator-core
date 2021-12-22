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


from typing import List, Union
from uuid import UUID

from more_itertools.more import one
from sqlalchemy.orm import joinedload

from orchestrator.db import ProductTable
from orchestrator.types import UUIDstr


def get_product_by_id(product_id: Union[UUID, UUIDstr]) -> ProductTable:
    """
    Get product by id.

    Args:
        product_id: ProductTable id uuid

    Returns: ProductTable object

    """
    return ProductTable.query.options(joinedload("fixed_inputs")).get(product_id)


def get_product_by_name(name: str) -> ProductTable:
    return ProductTable.query.options(joinedload("fixed_inputs")).filter(ProductTable.name == name).one()


def get_types() -> List[str]:
    return list(
        map(one, ProductTable.query.distinct(ProductTable.product_type).with_entities(ProductTable.product_type))
    )


def get_tags() -> List[str]:
    return list(map(one, ProductTable.query.distinct(ProductTable.tag).with_entities(ProductTable.tag)))
