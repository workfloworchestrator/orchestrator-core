from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy_utils import Ltree

from orchestrator import llm_settings
from orchestrator.db import ProcessStepTable, ProcessTable, WorkflowTable, db
from orchestrator.targets import Target
from orchestrator.utils.datetime import nowtz
from orchestrator.workflow import ProcessStatus
from test.unit_tests.workflows import assert_complete, assert_state, extract_state, run_workflow


@pytest.fixture
def task():
    three_weeks_ago = nowtz() - timedelta(weeks=3)
    two_weeks_ago = nowtz() - timedelta(weeks=2)
    state = {"foo": "bar"}

    generic_step = ProcessStepTable(name="generic-step", status="success", state=state)

    wf_old = WorkflowTable(
        workflow_id=uuid4(), name="nice and old task", description="nice and old task", target=Target.SYSTEM
    )
    task_old = ProcessTable(
        workflow_id=wf_old.workflow_id,
        last_status=ProcessStatus.COMPLETED,
        last_step="Awesome last step",
        started_at=three_weeks_ago,
        last_modified_at=two_weeks_ago,
        steps=[generic_step],
        is_task=True,
    )
    wf_new = WorkflowTable(
        workflow_id=uuid4(), name="nice and new task", description="nice and new task", target=Target.SYSTEM
    )

    task_new = ProcessTable(
        workflow_id=wf_new.workflow_id,
        last_status=ProcessStatus.COMPLETED,
        last_step="Awesome last step",
        started_at=three_weeks_ago,
        last_modified_at=nowtz(),
        steps=[generic_step],
        is_task=True,
    )
    wf = WorkflowTable(workflow_id=uuid4(), name="nice process", description="nice process", target=Target.SYSTEM)

    process = ProcessTable(
        workflow_id=wf.workflow_id,
        last_status=ProcessStatus.COMPLETED,
        last_step="Awesome last step",
        started_at=three_weeks_ago,
        last_modified_at=two_weeks_ago,
        steps=[generic_step],
        is_task=False,
    )
    db.session.add_all([wf_old, wf_new, wf, generic_step, task_old, task_new, process])
    db.session.commit()

    if llm_settings.SEARCH_ENABLED:
        from orchestrator.db.models import AiSearchIndex
        from orchestrator.search.core.types import EntityType, FieldType

        search_index_old_1 = AiSearchIndex(
            entity_type=EntityType.PROCESS,
            # match the entity_id with the task that is being deleted
            entity_id=task_old.process_id,
            entity_title="task_clean_up_task",
            path=Ltree("process.is_task"),
            value="True",
            content_hash="60c5df334e796463ac8865a83bcda791bb3ffb602585cfeca04bdb5ac5fab819",
            value_type=FieldType.BOOLEAN
        )
        search_index_old_2 = AiSearchIndex(
            entity_type=EntityType.PROCESS,
            # match the entity_id with the task that is being deleted
            entity_id=task_old.process_id,
            entity_title="task_clean_up_task",
            path=Ltree("process.workflow_id"),
            value=task_old.workflow_id,
            content_hash="7cd393121fba5e804010654555d522af55f3b691838bc4fd8a7d6cd5a19177fe",
            value_type=FieldType.UUID
        )
        non_matching_search_index = AiSearchIndex(
            entity_type=EntityType.PROCESS,
            # this one will not match
            entity_id=task_new.process_id,
            entity_title="task_clean_up_task",
            path=Ltree("process.is_task"),
            value="True",
            content_hash="50b5521b092f5d5d4add66add86de68549d47388c02e97cabc9e9696fba7320f",
            value_type=FieldType.BOOLEAN
        )
        db.session.add_all([search_index_old_1, search_index_old_2, non_matching_search_index])
        db.session.commit()


@pytest.mark.workflow
def test_remove_tasks(task):
    result, process, step_log = run_workflow("task_clean_up_tasks", {})
    assert_complete(result)
    res = extract_state(result)

    if llm_settings.SEARCH_ENABLED:
        state = {"process_id": res["process_id"], "reporter": "john.doe", "tasks_removed": 1,
                 'ai_search_index_rows_deleted': 2}

        from orchestrator.db.models import AiSearchIndex
        ai_indexes = db.session.scalars(select(AiSearchIndex)).all()
        # 2 deleted, 1 left
        assert len(ai_indexes) == 1

        assert_state(result, state)
        assert len(res['deleted_process_id_list']) == 1

    else:
        state = {"process_id": res["process_id"], "reporter": "john.doe", "tasks_removed": 1,
                 'ai_search_index_rows_deleted': 0, 'ai_search_enabled': False}

        assert_state(result, state)
        assert len(res['deleted_process_id_list']) == 1

    processes = db.session.scalars(select(ProcessTable)).all()

    assert len(processes) == 3
    assert sorted(p.workflow.name for p in processes) == sorted(
        ["nice and new task", "nice process", "task_clean_up_tasks"]
    )
