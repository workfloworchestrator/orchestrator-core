# Copyright 2022-2023 SURF.
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
from typing import Callable

# Map some Orchestrator types to scalars
import strawberry
from graphql import GraphQLError
from oauth2_lib.fastapi import OIDCUserModel
from strawberry.fastapi import BaseContext
from strawberry.types import Info
from strawberry.types.info import RootValueType


class CustomContext(BaseContext):
    def __init__(self, get_current_user: Callable[[], OIDCUserModel], get_opa_decision: Callable[[str], bool]):
        self.errors: list[GraphQLError] = []
        self.get_current_user = get_current_user
        self.get_opa_decision = get_opa_decision
        super().__init__()


CustomInfo = Info[CustomContext, RootValueType]


@strawberry.enum(description="Sort order (ASC or DESC)")
class SortOrder(Enum):
    ASC = "asc"
    DESC = "desc"


@strawberry.input(description="Sort resource by attribute")
class Sort:
    field: str = strawberry.field(description="Field to sort on")
    order: SortOrder = strawberry.field(default=SortOrder.ASC, description="Sort order (ASC or DESC")
