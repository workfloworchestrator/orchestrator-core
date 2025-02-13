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

from http import HTTPStatus
from uuid import UUID

from fastapi.param_functions import Body
from fastapi.routing import APIRouter

from orchestrator.api.error_handling import raise_status
from orchestrator.db import db
from orchestrator.db.models import ResourceTypeTable
from orchestrator.schemas.resource_type import ResourceTypePatchSchema, ResourceTypeSchema

router = APIRouter()


@router.get("/{resource_type_id}", response_model=ResourceTypeSchema)
def get_resource_type_description(resource_type_id: UUID) -> str:
    resource_type = db.session.get(ResourceTypeTable, resource_type_id)
    if resource_type is None:
        raise_status(HTTPStatus.NOT_FOUND)
    return resource_type


@router.patch("/{resource_type_id}", status_code=HTTPStatus.CREATED, response_model=ResourceTypeSchema)
async def patch_resource_type_by_id(
    resource_type_id: UUID, data: ResourceTypePatchSchema = Body(...)
) -> ResourceTypeTable:
    resource_type = db.session.get(ResourceTypeTable, resource_type_id)
    if not resource_type:
        raise_status(HTTPStatus.NOT_FOUND, f"ResourceType id {resource_type_id} not found")

    return await _patch_resource_type_description(data, resource_type)


async def _patch_resource_type_description(
    data: ResourceTypePatchSchema,
    resource_type: ResourceTypeTable,
) -> ResourceTypeTable:

    updated_properties = data.model_dump(exclude_unset=True)
    description = updated_properties.get("description", resource_type.description)
    resource_type.description = description
    db.session.commit()
    return resource_type
