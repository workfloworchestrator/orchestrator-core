# Copyright 2019-2026 SURF, GÉANT.
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

from typing import TYPE_CHECKING, Annotated

import strawberry

from orchestrator.core.db import ResourceTypeTable
from orchestrator.core.graphql.schemas.helpers import get_original_model
from orchestrator.core.schemas.resource_type import ResourceTypeSchema

if TYPE_CHECKING:
    from orchestrator.core.graphql.schemas.product_block import ProductBlock


@strawberry.experimental.pydantic.type(model=ResourceTypeSchema, all_fields=True)
class ResourceType:
    @strawberry.field(description="Return all product blocks that make use of this resource type")  # type: ignore
    async def product_blocks(self) -> list[Annotated["ProductBlock", strawberry.lazy(".product_block")]]:
        from orchestrator.core.graphql.schemas.product_block import ProductBlock

        model = get_original_model(self, ResourceTypeTable)
        return [ProductBlock.from_pydantic(product_block) for product_block in model.product_blocks]
