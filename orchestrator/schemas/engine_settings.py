# Copyright 2019-2020 SURF, GÉANT.
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


import strawberry
from pydantic import ConfigDict

from orchestrator.schemas.base import OrchestratorBaseModel
from pydantic_forms.types import strEnum


@strawberry.enum
class GlobalStatusEnum(strEnum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    PAUSING = "PAUSING"


class EngineSettingsBaseSchema(OrchestratorBaseModel):
    global_lock: bool


class WorkerStatus(OrchestratorBaseModel):
    executor_type: str
    number_of_workers_online: int = 0
    number_of_queued_jobs: int = 0
    number_of_running_jobs: int = 0


class EngineSettingsSchema(EngineSettingsBaseSchema):
    global_status: GlobalStatusEnum | None = None
    running_processes: int
    model_config = ConfigDict(from_attributes=True)
