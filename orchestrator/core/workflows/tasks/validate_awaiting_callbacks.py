# Copyright 2026 SURF.
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
from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from orchestrator.core.db import ProcessTable, db
from orchestrator.core.services import processes
from orchestrator.core.settings import get_authorizers
from orchestrator.core.targets import Target
from orchestrator.core.utils.datetime import nowtz
from orchestrator.core.workflow import CALLBACK_TIMEOUT_KEY, ProcessStatus, StepList, done, init, step, workflow
from orchestrator.core.workflows.predicates import awaiting_callbacks_exist
from pydantic_forms.types import State, UUIDstr

authorizers = get_authorizers()
logger = structlog.get_logger(__name__)


def _is_timed_out(process: ProcessTable, now: datetime) -> bool:
    """Return True when the process's awaiting callback step has a timeout that has elapsed.

    The deadline is anchored on the awaiting step's ``started_at`` column (the time the await began) and the timeout
    (seconds) is read from that step's state. A step without a ``__callback_timeout`` never times out.
    """
    last_step = process.steps[-1] if process.steps else None
    if last_step is None or last_step.started_at is None:
        return False
    timeout = last_step.state.get(CALLBACK_TIMEOUT_KEY)
    if timeout is None:
        return False
    return (now - last_step.started_at).total_seconds() > timeout


def _fail_if_still_awaiting(process_id: UUIDstr) -> UUIDstr | None:
    """Fail a single timed-out process, re-checking its status first to avoid racing an arriving callback."""
    process = db.session.get(ProcessTable, process_id)
    if process is None or process.last_status != ProcessStatus.AWAITING_CALLBACK:
        return None
    try:
        # Enable commit to be able to fail the process as normal
        db.session.enable_commit()
        processes.fail_awaiting_process(process)
        return process_id
    except Exception as exc:
        logger.warning("Could not fail timed-out awaiting process", process_id=process_id, error=str(exc))
        return None
    finally:
        # Make sure to disable commit again
        db.session.disable_commit()


@step("Find timed-out awaiting-callback processes")
def find_timed_out_callbacks(process_id: UUID) -> State:
    now = nowtz()
    awaiting_processes = db.session.scalars(
        select(ProcessTable)
        .options(selectinload(ProcessTable.steps))
        .filter(
            ProcessTable.last_status == ProcessStatus.AWAITING_CALLBACK,
            ProcessTable.process_id != process_id,
        )
    )
    timed_out_process_ids = [str(p.process_id) for p in awaiting_processes if _is_timed_out(p, now)]

    return {
        "number_of_timed_out_processes": len(timed_out_process_ids),
        "timed_out_process_ids": timed_out_process_ids,
    }


@step("Fail timed-out callbacks")
def fail_timed_out_callbacks(timed_out_process_ids: list[UUIDstr]) -> State:
    failed_process_ids = list(filter(None, map(_fail_if_still_awaiting, timed_out_process_ids)))

    return {
        "number_of_failed_process_ids": len(failed_process_ids),
        "failed_process_ids": failed_process_ids,
    }


@workflow(
    target=Target.SYSTEM,
    authorize_callback=authorizers.authorize_callback,
    retry_auth_callback=authorizers.retry_auth_callback,
    run_predicate=awaiting_callbacks_exist,
)
def task_validate_awaiting_callbacks() -> StepList:
    return init >> find_timed_out_callbacks >> fail_timed_out_callbacks >> done
