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
from uuid import UUID

import structlog
from sqlalchemy import select

from orchestrator.db import ProcessTable, db
from orchestrator.services import processes
from orchestrator.targets import Target
from orchestrator.workflow import ProcessStatus, StepList, done, init, step, workflow
from pydantic_forms.types import State, UUIDstr

logger = structlog.get_logger(__name__)


def get_process_ids_by_process_statuses(process_statuses: list[ProcessStatus], exclude_ids: list[UUID]) -> list:
    return list(
        db.session.scalars(
            select(ProcessTable.process_id).filter(
                ProcessTable.last_status.in_(process_statuses), ProcessTable.process_id.not_in(exclude_ids)
            )
        )
    )


@step("Find waiting workflows")
def find_waiting_workflows(process_id: UUID) -> State:
    created_process_ids = get_process_ids_by_process_statuses([ProcessStatus.CREATED], exclude_ids=[process_id])
    resumed_process_ids = get_process_ids_by_process_statuses([ProcessStatus.RESUMED], exclude_ids=[process_id])
    waiting_process_ids = get_process_ids_by_process_statuses([ProcessStatus.WAITING], exclude_ids=[process_id])

    return {
        "number_of_waiting_processes": len(waiting_process_ids),
        "waiting_process_ids": waiting_process_ids,
        "created_processes_stuck": len(created_process_ids),
        "created_state_process_ids": created_process_ids,
        "resumed_processes_stuck": len(resumed_process_ids),
        "resumed_state_process_ids": resumed_process_ids,
    }


@step("Resume found workflows")
def resume_found_workflows(
    waiting_process_ids: list[UUIDstr],
    resumed_state_process_ids: list[UUIDstr],
) -> State:
    resume_processes = waiting_process_ids + resumed_state_process_ids

    resumed_process_ids: list = []
    for process_id in resume_processes:
        try:
            process = db.session.get(ProcessTable, process_id)
            if not process:
                continue

            # Workaround the commit disable function
            db.session.info["disabled"] = False

            processes.resume_process(process)
            resumed_process_ids.append(process_id)
        except Exception as exc:
            logger.warning("Could not resume process", process_id=process_id, error=str(exc))
        finally:
            # Make sure to turn it on again
            db.session.info["disabled"] = True

    return {
        "number_of_resumed_process_ids": len(resumed_process_ids),
        "resumed_process_ids": resumed_process_ids,
    }


@step("Restart found CREATED workflows")
def restart_created_workflows(created_state_process_ids: list[UUIDstr]) -> State:
    started_process_ids = []
    for process_id in created_state_process_ids:
        try:
            process = db.session.get(ProcessTable, process_id)
            if not process:
                continue

            # Workaround the commit disable function
            db.session.info["disabled"] = False

            processes.restart_process(process)
            started_process_ids.append(process_id)
        except Exception as exc:
            logger.warning("Could not resume process", process_id=process_id, error=str(exc))
        finally:
            # Make sure to turn it on again
            db.session.info["disabled"] = True

    return {
        "number_of_started_process_ids": len(started_process_ids),
        "started_process_ids": started_process_ids,
    }


@workflow(
    "Resume all workflows that are stuck on tasks with the status 'waiting', 'created' or 'resumed'",
    target=Target.SYSTEM,
)
def task_resume_workflows() -> StepList:
    return init >> find_waiting_workflows >> resume_found_workflows >> restart_created_workflows >> done
