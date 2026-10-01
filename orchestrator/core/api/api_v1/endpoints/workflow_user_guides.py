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

from http import HTTPStatus

from fastapi.exceptions import HTTPException
from fastapi.routing import APIRouter

from nwastdlib.file_utils import PathOutsideRootError, SafeName
from orchestrator.core.services.workflow_user_guides import get_workflow_guide

router = APIRouter()


@router.get("/{workflow_name}", response_model=str)
async def get_workflow_guide_by_name(
    workflow_name: SafeName,
) -> str:
    try:
        guide = await get_workflow_guide(workflow_name)
    except PathOutsideRootError:
        # Do not reveal whether a name resolves outside the guide directory or is simply missing.
        guide = None
    if guide is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Workflow guide not found")
    return guide
