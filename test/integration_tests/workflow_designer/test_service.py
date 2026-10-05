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

import pytest
from sqlalchemy import func, select, text

from orchestrator.core.db import WorkflowTable, db
from orchestrator.core.targets import Target
from orchestrator.core.workflow import ProcessStatus
from orchestrator.core.workflow_designer.service import (
    DesignerError,
    create_workflow,
    delete_workflow,
    get_workflow_definition,
    update_workflow,
)
from orchestrator.core.workflow_designer.source import designed_workflows
from orchestrator.core.workflows import all_workflow_names, get_workflow
from test.integration_tests.workflow_designer.conftest import REPORT, add_process


def _row(name: str, include_deleted: bool = False) -> WorkflowTable | None:
    stmt = select(WorkflowTable) if include_deleted else WorkflowTable.select()
    return db.session.scalars(stmt.where(WorkflowTable.name == name)).one_or_none()


def test_create_makes_a_resolvable_task():
    stored = create_workflow(REPORT, user="jane")

    row = _row(REPORT.name)
    assert (row.target, row.is_task, row.description) == (Target.SYSTEM, True, REPORT.description)
    assert (stored.version, stored.created_by, stored.process_count) == (1, "jane", 0)
    assert [step.name for step in get_workflow(REPORT.name).steps] == [
        "Start",
        "Store note",
        "Set checked_by",
        "Log message",
        "Done",
    ]
    assert REPORT.name in all_workflow_names()


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("designed_note_report", id="designed"),
        pytest.param("designed_archived", id="soft-deleted"),
    ],
)
def test_create_rejects_taken_names(name):
    create_workflow(REPORT.model_copy(update={"name": "designed_archived"}), user="jane")
    add_process("designed_archived", ProcessStatus.COMPLETED)
    delete_workflow("designed_archived")
    create_workflow(REPORT, user="jane")

    with pytest.raises(DesignerError) as error:
        create_workflow(REPORT.model_copy(update={"name": name}), user="jane")
    assert error.value.status == "conflict"


def test_create_rejects_invalid_chain():
    with pytest.raises(DesignerError) as error:
        create_workflow(REPORT.model_copy(update={"form_fields": []}), user="jane")

    assert error.value.status == "invalid"
    assert _row(REPORT.name, include_deleted=True) is None


def test_update_rebuilds_in_place():
    create_workflow(REPORT, user="jane")
    first = get_workflow(REPORT.name)

    stored = update_workflow(REPORT.name, REPORT.model_copy(update={"steps": REPORT.steps[:1]}))

    assert stored.version == 2
    rebuilt = get_workflow(REPORT.name)
    assert rebuilt is not first
    assert [step.name for step in rebuilt.steps] == ["Start", "Store note", "Done"]


@pytest.mark.parametrize(
    ("status", "allowed"),
    [
        pytest.param(ProcessStatus.SUSPENDED, False, id="suspended"),
        pytest.param(ProcessStatus.FAILED, False, id="failed"),
        pytest.param(ProcessStatus.COMPLETED, True, id="completed"),
        pytest.param(ProcessStatus.ABORTED, True, id="aborted"),
    ],
)
def test_update_and_delete_wait_for_unfinished_processes(status, allowed):
    create_workflow(REPORT, user="jane")
    add_process(REPORT.name, status)

    if allowed:
        assert update_workflow(REPORT.name, REPORT).version == 2
    else:
        for change in (lambda: update_workflow(REPORT.name, REPORT), lambda: delete_workflow(REPORT.name)):
            with pytest.raises(DesignerError) as error:
                change()
            assert error.value.status == "conflict"


@pytest.mark.parametrize(
    ("status", "result", "row_kept"),
    [
        pytest.param(None, "deleted", False, id="no-processes"),
        pytest.param(ProcessStatus.COMPLETED, "archived", True, id="keeps-history"),
    ],
)
def test_delete(status, result, row_kept):
    create_workflow(REPORT, user="jane")
    get_workflow(REPORT.name)
    if status:
        add_process(REPORT.name, status)

    assert delete_workflow(REPORT.name) == result

    assert get_workflow(REPORT.name) is None
    assert REPORT.name not in designed_workflows.names()
    assert (_row(REPORT.name, include_deleted=True) is not None) is row_kept
    with pytest.raises(DesignerError):
        get_workflow_definition(REPORT.name)


def test_renaming_is_not_an_update():
    create_workflow(REPORT, user="jane")

    with pytest.raises(DesignerError) as error:
        update_workflow(REPORT.name, REPORT.model_copy(update={"name": "designed_other"}))
    assert error.value.status == "invalid"


def test_stored_definition_that_no_longer_parses_still_lists():
    create_workflow(REPORT, user="jane")
    db.session.execute(text("UPDATE workflow_designer_definitions SET definition = '{\"name\": 1}'"))
    db.session.commit()

    workflow = get_workflow(REPORT.name)

    assert workflow is not None
    assert [step.name for step in workflow.steps] == ["Start", f"Unavailable step {REPORT.name}", "Done"]


def test_failing_lookup_does_not_abort_the_callers_transaction():
    from orchestrator.core.workflow_designer import source

    def missing_table():
        db.session.execute(text("SELECT * FROM table_that_does_not_exist"))

    assert source._execute_safely(missing_table, default="fallback") == "fallback"
    assert db.session.scalar(select(func.count()).select_from(WorkflowTable)) >= 0
