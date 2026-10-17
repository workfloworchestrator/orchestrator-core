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

"""Create, change and remove designed workflows.

A designed workflow is a `workflows` row (so the engine can start, list and schedule it like any task) plus its
definition. Cached workflows of this process are only invalidated after the database commit; other processes notice
the new version on their next lookup.
"""

from dataclasses import dataclass
from typing import Literal

import structlog
from sqlalchemy import delete, func, select

from orchestrator.core.db import ProcessTable, WorkflowTable, db
from orchestrator.core.db.database import transactional
from orchestrator.core.db.models import WorkflowDesignerDefinitionTable
from orchestrator.core.targets import Target
from orchestrator.core.utils.datetime import nowtz
from orchestrator.core.workflow import ProcessStatus
from orchestrator.core.workflow_designer.definition import ValidationResult, WorkflowDefinition, validate_definition
from orchestrator.core.workflow_designer.discovery import discover_steps
from orchestrator.core.workflow_designer.source import designed_workflows
from orchestrator.core.workflows import ALL_WORKFLOWS

logger = structlog.get_logger(__name__)

# Processes in these states will not run another step, so changing the step list cannot misalign them on resume.
FINISHED_STATUSES = {ProcessStatus.COMPLETED, ProcessStatus.ABORTED}


class DesignerError(Exception):
    def __init__(self, message: str, status: Literal["not_found", "conflict", "invalid"], detail: object = None):
        super().__init__(message)
        self.status = status
        self.detail = detail


@dataclass
class StoredWorkflow:
    definition: WorkflowDefinition
    version: int
    created_by: str | None
    process_count: int


def _definition_row(name: str) -> WorkflowDesignerDefinitionTable | None:
    stmt = (
        select(WorkflowDesignerDefinitionTable)
        .join(WorkflowTable)
        .where(WorkflowTable.name == name, WorkflowTable.deleted_at.is_(None))
    )
    return db.session.scalars(stmt).one_or_none()


def _process_counts(workflow_id: object) -> tuple[int, int]:
    """(all processes, unfinished processes) of a workflow."""
    unfinished = func.count().filter(ProcessTable.last_status.not_in(FINISHED_STATUSES))
    stmt = select(func.count(), unfinished).where(ProcessTable.workflow_id == workflow_id)
    total, open_count = db.session.execute(stmt).one()
    return total, open_count


def _require_valid(definition: WorkflowDefinition) -> ValidationResult:
    result = validate_definition(definition, discover_steps())
    if not result.valid:
        raise DesignerError("The workflow definition is not valid", "invalid", result.model_dump(mode="json"))
    return result


def list_workflows() -> list[StoredWorkflow]:
    stmt = (
        select(WorkflowDesignerDefinitionTable)
        .join(WorkflowTable)
        .where(WorkflowTable.deleted_at.is_(None))
        .order_by(WorkflowTable.name)
    )
    return [
        StoredWorkflow(
            definition=WorkflowDefinition.model_validate(row.definition),
            version=row.version,
            created_by=row.created_by,
            process_count=_process_counts(row.workflow_id)[0],
        )
        for row in db.session.scalars(stmt)
    ]


def get_workflow_definition(name: str) -> StoredWorkflow:
    row = _definition_row(name)
    if row is None:
        raise DesignerError(f"Designed workflow '{name}' does not exist", "not_found")
    return StoredWorkflow(
        definition=WorkflowDefinition.model_validate(row.definition),
        version=row.version,
        created_by=row.created_by,
        process_count=_process_counts(row.workflow_id)[0],
    )


def create_workflow(definition: WorkflowDefinition, user: str) -> StoredWorkflow:
    _require_valid(definition)
    # The unique constraint on `workflows.name` includes soft deleted rows, so those names stay taken.
    name_taken = db.session.scalar(select(func.count()).where(WorkflowTable.name == definition.name))
    if definition.name in ALL_WORKFLOWS or name_taken:
        raise DesignerError(f"A workflow named '{definition.name}' already exists", "conflict")

    with transactional(db, logger):
        workflow = WorkflowTable(
            name=definition.name, target=Target.SYSTEM, description=definition.description, is_task=True
        )
        db.session.add(workflow)
        db.session.flush()
        db.session.add(
            WorkflowDesignerDefinitionTable(
                workflow_id=workflow.workflow_id,
                definition=definition.model_dump(mode="json"),
                version=1,
                created_by=user,
            )
        )

    designed_workflows.invalidate(definition.name)
    return StoredWorkflow(definition=definition, version=1, created_by=user, process_count=0)


def update_workflow(name: str, definition: WorkflowDefinition) -> StoredWorkflow:
    if definition.name != name:
        raise DesignerError("A designed workflow cannot be renamed; create a new one instead", "invalid")
    _require_valid(definition)
    row = _definition_row(name)
    if row is None:
        raise DesignerError(f"Designed workflow '{name}' does not exist", "not_found")
    total, unfinished = _process_counts(row.workflow_id)
    if unfinished:
        # Resume matches steps by position, so a changed step list would skip or repeat steps of these processes.
        raise DesignerError(f"'{name}' has {unfinished} unfinished process(es); finish or abort them first", "conflict")

    with transactional(db, logger):
        row.definition = definition.model_dump(mode="json")
        row.version = row.version + 1
        row.updated_at = nowtz()
        row.workflow.description = definition.description
        version = row.version

    designed_workflows.invalidate(name)
    return StoredWorkflow(definition=definition, version=version, created_by=row.created_by, process_count=total)


def delete_workflow(name: str) -> Literal["deleted", "archived"]:
    """Delete a workflow without processes; archive (soft delete) one that has them, to keep their history."""
    row = _definition_row(name)
    if row is None:
        raise DesignerError(f"Designed workflow '{name}' does not exist", "not_found")
    workflow_id = row.workflow_id
    total, unfinished = _process_counts(workflow_id)
    if unfinished:
        raise DesignerError(f"'{name}' has {unfinished} unfinished process(es); finish or abort them first", "conflict")

    with transactional(db, logger):
        if total:
            row.workflow.deleted_at = nowtz()
            row.updated_at = nowtz()
        else:
            # A Core delete: the ORM relationship would cascade to processes (there are none, but be explicit).
            db.session.execute(delete(WorkflowTable).where(WorkflowTable.workflow_id == workflow_id))

    designed_workflows.invalidate(name)
    return "archived" if total else "deleted"
