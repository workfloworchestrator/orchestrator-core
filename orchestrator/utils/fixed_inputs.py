# Copyright 2019-2024 SURF.
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

from enum import Enum
from typing import Any

from more_itertools import first_true, one
from sqlalchemy.exc import NoResultFound
from structlog import get_logger

from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.services import products

logger = get_logger(__name__)


def fixed_input_configuration() -> dict[str, Any]:  # noqa: C901
    product_tags = products.get_tags()

    data: dict = {"fixed_inputs": [], "by_tag": {}}
    for tag in product_tags:
        data["by_tag"][tag] = []

    for product_name, model in SUBSCRIPTION_MODEL_REGISTRY.items():
        try:
            product = products.get_product_by_name(product_name)
        except NoResultFound:
            logger.error(
                "Couldn't resolve product with fixed inputs for a domain model, due to a product_name " "mismatch.",
                product_name=product_name,
            )

        for fi_name, fi_type in model._non_product_block_fields_.items():
            fi_data = first_true(data["fixed_inputs"], None, lambda i: i["name"] == fi_name)  # noqa: B023
            if not fi_data:
                if issubclass(fi_type, Enum):
                    data["fixed_inputs"].append(
                        {
                            "name": fi_name,
                            "description": (fi_type.__doc__ or fi_name).splitlines()[0],
                            "values": list(map(lambda v: str(v.value), fi_type)),
                        }
                    )
                else:
                    raise ValueError(f"{fi_name} of {product_name} should be an enum.")

            if not first_true(data["by_tag"][product.tag], None, lambda i: fi_name in i):  # noqa: B023
                data["by_tag"][product.tag].append({fi_name: True})

    # Check if required
    for product_name, model in SUBSCRIPTION_MODEL_REGISTRY.items():
        product = products.get_product_by_name(product_name)

        for fi in data["by_tag"][product.tag]:
            if one(fi) not in model._non_product_block_fields_:
                fi[one(fi)] = False

    return data
