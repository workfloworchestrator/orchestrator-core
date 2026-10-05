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

"""Resolve designed workflows from the database, for `orchestrator.core.workflows.get_workflow`.

This module is imported while `orchestrator.core.workflows` loads, so it only imports what that module already
depends on (settings, db, the workflow DSL). Building a workflow needs much more (forms, discovery) and is imported when
it is first needed.
"""

import threading
from typing import Any
from uuid import UUID

import structlog
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from orchestrator.core.db import WorkflowTable, db, wrapped_db
from orchestrator.core.db.database import Database
from orchestrator.core.db.models import WorkflowDesignerDefinitionTable
from orchestrator.core.settings import app_settings
from orchestrator.core.workflow import Workflow

logger = structlog.get_logger(__name__)


def _db_configured() -> bool:
    # Without a database (unit tests, tooling) `db.session` raises; there are no designed workflows then.
    return isinstance(wrapped_db.wrapped_database, Database)


class DesignedWorkflowSource:
    """Workflows designed in the GUI, stored in `workflow_designer_definitions`.

    Built workflows are cached per name. The cache is keyed on the row's workflow_id and version, so an update, or a
    delete and re-create under the same name, rebuilds the workflow in every process without any signalling between
    them.
    """

    def __init__(self) -> None:
        self._cache: dict[str, tuple[tuple[UUID, int], Workflow]] = {}
        self._lock = threading.Lock()

    def get(self, name: str) -> Workflow | None:
        if not name.startswith(app_settings.WORKFLOW_DESIGNER_NAME_PREFIX) or not _db_configured():
            return None
        if (row := _fetch_definition(name)) is None:
            self.invalidate(name)
            return None

        workflow_id, version, definition = row
        key = (workflow_id, version)
        with self._lock:
            if (cached := self._cache.get(name)) and cached[0] == key:
                return cached[1]
            workflow = _build(name, definition)
            self._cache[name] = (key, workflow)
            return workflow

    def names(self) -> set[str]:
        if not _db_configured():
            return set()
        stmt = (
            select(WorkflowTable.name)
            .join(
                WorkflowDesignerDefinitionTable,
                WorkflowDesignerDefinitionTable.workflow_id == WorkflowTable.workflow_id,
            )
            .where(WorkflowTable.deleted_at.is_(None))
        )
        return set(_execute_safely(lambda: db.session.scalars(stmt).all(), default=[]))

    def invalidate(self, name: str | None = None) -> None:
        """Forget built workflows, e.g. after the definition or the authorizer changed in this process."""
        with self._lock:
            if name is None:
                self._cache.clear()
            else:
                self._cache.pop(name, None)


def _execute_safely(query: Any, default: Any) -> Any:
    # A savepoint, so that a failing query never leaves the caller's transaction (a request, a workflow step) aborted.
    try:
        with db.session.begin_nested():
            return query()
    except ProgrammingError as exc:
        # The core migration that creates the table has not run (yet); behave as if nothing was designed.
        logger.warning("Designed workflows are unavailable", error=str(exc).splitlines()[0])
        return default


def _fetch_definition(name: str) -> tuple[UUID, int, dict[str, Any]] | None:
    stmt = (
        select(
            WorkflowTable.workflow_id,
            WorkflowDesignerDefinitionTable.version,
            WorkflowDesignerDefinitionTable.definition,
        )
        .join(WorkflowDesignerDefinitionTable, WorkflowDesignerDefinitionTable.workflow_id == WorkflowTable.workflow_id)
        .where(WorkflowTable.name == name, WorkflowTable.deleted_at.is_(None))
    )
    row = _execute_safely(lambda: db.session.execute(stmt).one_or_none(), default=None)
    return (row.workflow_id, row.version, row.definition) if row else None


def _build(name: str, definition: dict[str, Any]) -> Workflow:
    from orchestrator.core.workflow_designer.builder import build_invalid_workflow, build_workflow
    from orchestrator.core.workflow_designer.definition import WorkflowDefinition

    try:
        return build_workflow(WorkflowDefinition.model_validate(definition))
    except ValidationError as exc:
        logger.error("Stored workflow definition is invalid", name=name, error=str(exc))
        return build_invalid_workflow(name, f"its stored definition is invalid: {exc}")


designed_workflows = DesignedWorkflowSource()
