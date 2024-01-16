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
from typing import Optional

from sqlalchemy import select

from orchestrator.db import ResourceTypeTable, db


def get_resource_types(*, filters: Optional[list] = None) -> list[ResourceTypeTable]:
    stmt = select(ResourceTypeTable)
    for clause in filters or []:
        stmt = stmt.where(clause)
    return list(db.session.scalars(stmt))
