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

"""Schedules in the search index: indexing through the shared indexer, removal, export and id lookup.

Embeddings are disabled in the tests, so indexing stores the fields without calling an embedding service.
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.schedules.scheduler import get_scheduler
from orchestrator.core.schedules.service import _delete_linker_entry, index_schedule
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.entity_lookup import ResolvedEntity, resolve_entity_id_prefix
from orchestrator.core.search.indexing import run_indexing_for_entity
from orchestrator.core.search.query.export import fetch_export_data
from orchestrator.core.services.workflows import get_workflow_by_name

pytestmark = pytest.mark.search

WORKFLOW_NAME = "task_resume_workflows"


def _indexed_fields(schedule_id: str) -> dict[str, str]:
    stmt = select(AiSearchIndex.path, AiSearchIndex.value).where(
        AiSearchIndex.entity_type == EntityType.SCHEDULE.value, AiSearchIndex.entity_id == UUID(schedule_id)
    )
    return {str(path): value for path, value in db.session.execute(stmt)}


@pytest.fixture
def schedule_id(clear_all_scheduler_jobs, create_schedules_via_api) -> str:
    """A schedule as the API makes it: an APScheduler job with a linker entry."""
    clear_all_scheduler_jobs()
    schedule_id = str(uuid4())
    create_schedules_via_api(job_name="Resume nightly", workflow_name=WORKFLOW_NAME, schedule_id=schedule_id)
    return schedule_id


def test_index_schedule_indexes_the_workflow_and_the_job(schedule_id):
    workflow = get_workflow_by_name(WORKFLOW_NAME)

    index_schedule(schedule_id)

    fields = _indexed_fields(schedule_id)
    next_run_time = fields.pop("schedule.next_run_time")
    assert next_run_time
    assert fields == {
        "schedule.schedule_id": schedule_id,
        "schedule.name": "Resume nightly",
        "schedule.trigger": "interval[1:00:00]",
        "schedule.workflow_id": str(workflow.workflow_id),
        "schedule.workflow_name": WORKFLOW_NAME,
        "schedule.workflow_description": workflow.description,
        "schedule.workflow_target": "SYSTEM",
        "schedule.is_task": "True",
    }


def test_index_schedule_indexes_the_subscription_id(schedule_id, product_type_1_subscription_factory):
    subscription_id = product_type_1_subscription_factory(description="Scheduled maintenance subscription")
    with get_scheduler() as scheduler:
        scheduler.get_job(schedule_id).modify(
            kwargs={"workflow_name": WORKFLOW_NAME, "user_inputs": [{"subscription_id": subscription_id}]}
        )

    index_schedule(schedule_id)

    fields = _indexed_fields(schedule_id)
    assert fields["schedule.subscription_id"] == subscription_id
    assert "schedule.subscription_description" not in fields


def test_index_schedule_removes_a_schedule_that_no_longer_exists(schedule_id):
    index_schedule(schedule_id)
    workflow = get_workflow_by_name(WORKFLOW_NAME)
    _delete_linker_entry(workflow_id=workflow.workflow_id, schedule_id=schedule_id)

    index_schedule(schedule_id)

    assert _indexed_fields(schedule_id) == {}


def test_indexing_the_entity_type_indexes_every_linked_schedule(schedule_id, scheduler_with_jobs):
    # A job without a linker entry, as the deprecated scheduler decorator makes them, is not a schedule
    unlinked_job_id = str(uuid4())
    scheduler_with_jobs(schedule_id=unlinked_job_id)

    run_indexing_for_entity(EntityType.SCHEDULE)

    assert _indexed_fields(schedule_id)["schedule.name"] == "Resume nightly"
    assert _indexed_fields(unlinked_job_id) == {}


def test_schedule_export_returns_the_indexed_fields(schedule_id):
    workflow = get_workflow_by_name(WORKFLOW_NAME)

    (export,) = fetch_export_data(EntityType.SCHEDULE, [schedule_id, str(uuid4())])

    assert export.pop("next_run_time")
    assert export == {
        "schedule_id": schedule_id,
        "name": "Resume nightly",
        "trigger": "interval[1:00:00]",
        "workflow_id": str(workflow.workflow_id),
        "workflow_name": WORKFLOW_NAME,
        "workflow_description": workflow.description,
        "workflow_target": "SYSTEM",
        "is_task": True,
        "subscription_id": None,
    }


async def test_schedule_id_prefix_resolves_to_the_workflow_name(schedule_id, async_session):
    resolved = await resolve_entity_id_prefix(async_session, EntityType.SCHEDULE, schedule_id[:8], limit=5)

    assert resolved == [ResolvedEntity(entity_id=schedule_id, title=WORKFLOW_NAME)]
