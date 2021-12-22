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

from typing import Optional
from uuid import UUID

from orchestrator.schemas.base import OrchestratorBaseModel


class ResourceTypeBaseSchema(OrchestratorBaseModel):
    resource_type: str
    description: Optional[str]
    resource_type_id: Optional[UUID]


class ResourceTypeSchema(ResourceTypeBaseSchema):
    resource_type_id: UUID


class ResourceTypeSchemaORM(ResourceTypeSchema):
    class Config:
        orm_mode = True
