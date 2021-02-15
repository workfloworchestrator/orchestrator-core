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

from typing import List

import structlog

from orchestrator.db import ProcessTable, db
from orchestrator.services import processes
from orchestrator.targets import Target
from orchestrator.types import State, UUIDstr
from orchestrator.workflow import ProcessStatus, StepList, done, init, step, workflow

logger = structlog.get_logger(__name__)


@step("Find waiting workflows")
def find_waiting_workflows() -> State:
    processes = ProcessTable.query.filter(ProcessTable.last_status == ProcessStatus.WAITING).all()
    waiting_pids = [str(process.pid) for process in processes]
    return {"number_of_waiting_processes": len(waiting_pids), "waiting_pids": waiting_pids}


@step("Resume found workflows")
def resume_found_workflows(waiting_pids: List[UUIDstr]) -> State:
    resumed_pids = []
    for pid in waiting_pids:
        try:
            process = ProcessTable.query.get(pid)
            # Workaround the commit disable function
            db.session.info["disabled"] = False
            processes.resume_process(process)
            resumed_pids.append(pid)
        except Exception:
            logger.exception()
        finally:
            # Make sure to turn it on again
            db.session.info["disabled"] = True

    return {"number_of_resumed_pids": len(resumed_pids), "resumed_pids": resumed_pids}


@workflow("Resume all workflows that are stuck on tasks with the status 'waiting'", target=Target.SYSTEM)
def task_resume_workflows() -> StepList:
    return init >> find_waiting_workflows >> resume_found_workflows >> done
