"""Stress / integration tests for parallel step execution.

These tests exercise complex compositions of parallel() and foreach_parallel():
nested parallelism, mixed types, asymmetric branches, scale, error propagation,
and edge cases. All tests run with real DB persistence via the engine-pool
session fixture.
"""

from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import close_all_sessions, sessionmaker

from orchestrator.db import ProcessStepRelationTable, ProcessStepTable, ProcessTable, db
from orchestrator.db.database import SESSION_ARGUMENTS, BaseModel, SearchQuery
from orchestrator.services.processes import SYSTEM_USER
from orchestrator.workflow import (
    ProcessStat,
    ProcessStatus,
    Success,
)
from test.unit_tests.workflows import (
    WorkflowInstanceForTests,
)


@pytest.fixture(autouse=True)
def db_session(database):
    """Use the engine's connection pool so each thread gets its own connection."""
    db.wrapped_database.session_factory = sessionmaker(**SESSION_ARGUMENTS, bind=db.wrapped_database.engine)
    db.wrapped_database.scoped_session = scoped_session(db.session_factory, db._scopefunc)
    BaseModel.set_query(cast(SearchQuery, db.wrapped_database.scoped_session.query_property()))
    try:
        yield
    finally:
        close_all_sessions()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

_wf_counter = 0


def register_test_workflow(wf):
    """Register a workflow for testing and return a WorkflowInstanceForTests context manager."""
    global _wf_counter
    _wf_counter += 1
    return WorkflowInstanceForTests(wf, f"test_parallel_stress_{_wf_counter}")


def create_new_process_stat(wf_table, initial_state):
    """Create a ProcessTable row and return a ProcessStat ready for runwf."""
    from orchestrator.workflows import get_workflow

    process_id = uuid4()
    p = ProcessTable(
        process_id=process_id,
        workflow_id=wf_table.workflow_id,
        last_status=ProcessStatus.CREATED,
        created_by=SYSTEM_USER,
        is_task=wf_table.is_task,
    )
    db.session.add(p)
    db.session.commit()
    wf_obj = get_workflow(wf_table.name)
    return ProcessStat(
        process_id=process_id,
        workflow=wf_obj,
        state=Success(initial_state),
        log=wf_obj.steps,
        current_user=SYSTEM_USER,
    )


def store(log):
    """Return a step-log callback that appends (step_name, process) tuples to *log*."""

    def _store(_pstat, step_, process):
        state = process.unwrap()
        step_name = state.pop("__step_name_override", step_.name)
        for k in [*state.get("__remove_keys", []), "__remove_keys"]:
            state.pop(k, None)
        if state.pop("__replace_last_state", None):
            log[-1] = (step_name, process)
        else:
            log.append((step_name, process))
        return process

    return _store


# ---------------------------------------------------------------------------
# DB query helpers
# ---------------------------------------------------------------------------


def _get_fork_steps(process_id):
    """Return all fork steps for a given process."""
    return (
        db.session.query(ProcessStepTable)
        .filter(
            ProcessStepTable.process_id == process_id,
            ProcessStepTable.parallel_total_branches.isnot(None),
        )
        .all()
    )


def _get_relations(parent_step_id):
    """Return all relation rows for a fork step, ordered by branch_index then order_id."""
    return (
        db.session.query(ProcessStepRelationTable)
        .filter(ProcessStepRelationTable.parent_step_id == parent_step_id)
        .order_by(ProcessStepRelationTable.branch_index, ProcessStepRelationTable.order_id)
        .all()
    )
