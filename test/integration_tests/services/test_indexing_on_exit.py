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

"""Integration tests asserting that processes and subscriptions are indexed when a process exits.

These run the real indexer against the real database and assert on the rows it writes to
`ai_search_index`. Asserting that `run_indexing_for_entity` was called would only restate the
hook's implementation; asserting the persisted row carries the terminal status is what pins the
bug this change fixes. No embedding service is needed: `EMBEDDING_API_ENABLED` is off by default.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from nwastdlib import const
from orchestrator.core.config.assignee import Assignee
from orchestrator.core.db import ProcessTable, db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.indexing import tasks as indexing_tasks
from orchestrator.core.services.processes import abort_process, fail_awaiting_process, start_process
from orchestrator.core.targets import Target
from orchestrator.core.utils.datetime import nowtz
from orchestrator.core.workflow import ProcessStatus, callback_step, done, init, inputstep, step, workflow
from orchestrator.core.workflows.steps import refresh_process_search_index, refresh_subscription_search_index
from pydantic_forms.core import FormPage
from pydantic_forms.types import UUIDstr
from test.integration_tests.workflows import WorkflowInstanceForTests, assert_aborted

pytestmark = pytest.mark.search


@step("Succeeding step")
def succeeding_step():
    return {"result": "ok"}


@step("Failing step")
def failing_step():
    raise ValueError("step blew up")


@step("Store subscription id")
def store_subscription_id_step(subscription_id):
    return {"subscription_id": subscription_id}


@inputstep("Wait for user input", assignee=Assignee.SYSTEM)
def suspending_step():
    class ConfirmForm(FormPage):
        confirm: bool = True

    user_input = yield ConfirmForm
    return user_input.model_dump()


class SubscriptionForm(FormPage):
    subscription_id: UUIDstr


# No description argument: passing one triggers the deprecation warning in workflow.py:600.
@workflow(target=Target.SYSTEM)
def indexing_success_wf():
    return init >> succeeding_step >> done


@workflow(target=Target.SYSTEM)
def indexing_failure_wf():
    return init >> failing_step >> done


# Suspends on the inputstep, so `start_process` returns with the process still SUSPENDED. That is a
# prerequisite for the abort test: `abort_wf` early-returns unchanged on an already-complete state.
@workflow(target=Target.SYSTEM)
def indexing_abort_wf():
    return init >> succeeding_step >> suspending_step >> done


@workflow(target=Target.SYSTEM, initial_input_form=const(SubscriptionForm))
def indexing_subscription_wf():
    return init >> store_subscription_id_step >> done


# Mimics a downstream workflow that has not yet dropped the deprecated refresh steps.
@workflow(target=Target.SYSTEM, initial_input_form=const(SubscriptionForm))
def indexing_legacy_steps_wf():
    return (
        init >> store_subscription_id_step >> refresh_subscription_search_index >> refresh_process_search_index >> done
    )


@step("Call external system")
def calling_step():
    return {}


@step("Validate callback result")
def validating_step():
    return {}


# Awaits a callback that never arrives, so the process parks in AWAITING_CALLBACK until the
# timeout sweep fails it. Keeps `subscription_id` in state, which `fail_awaiting_wf` preserves.
@workflow(target=Target.SYSTEM, initial_input_form=const(SubscriptionForm))
def indexing_timeout_wf():
    return (
        init
        >> store_subscription_id_step
        >> callback_step(
            name="Await external system",
            action_step=calling_step,
            validate_step=validating_step,
            timeout=300,
        )
        >> done
    )


def _backdate_await_step(process_id: UUIDstr, seconds: int) -> None:
    """Move the awaiting step's started_at into the past so its timeout counts as elapsed."""
    process = db.session.get(ProcessTable, process_id)
    assert process is not None
    await_step = process.steps[-1]
    await_step.started_at = nowtz() - timedelta(seconds=seconds)
    db.session.add(await_step)
    db.session.commit()


def _indexed_values(entity_id: UUIDstr) -> dict[str, str]:
    """Return what the search index actually holds for an entity, as {path: value}."""
    rows = db.session.scalars(select(AiSearchIndex).where(AiSearchIndex.entity_id == entity_id)).all()
    return {str(row.path): row.value for row in rows}


# Every database assertion stays inside the `WorkflowInstanceForTests` block: leaving it deletes the
# WorkflowTable row, which cascades (`WorkflowTable.processes`, delete-orphan) to the process under test.


@pytest.mark.parametrize(
    "workflow_func,workflow_name,expected_status",
    [
        pytest.param(indexing_success_wf, "indexing_success_wf", ProcessStatus.COMPLETED, id="completed"),
        pytest.param(indexing_failure_wf, "indexing_failure_wf", ProcessStatus.FAILED, id="failed"),
    ],
)
def test_exited_process_is_indexed_with_its_terminal_status(workflow_func, workflow_name, expected_status):
    """The indexed row must carry the terminal status, not the "running" it had mid-workflow.

    That stale status is the defect this change fixes, and the persisted row is the only place it
    is observable: indexing before the commit would store "running" here while the process table
    still ends up correct.
    """
    with WorkflowInstanceForTests(workflow_func, workflow_name):
        process_id = start_process(workflow_name, [{}])

        assert db.session.get(ProcessTable, process_id).last_status == expected_status
        assert _indexed_values(process_id)["process.last_status"] == expected_status


def test_aborted_process_is_indexed():
    with WorkflowInstanceForTests(indexing_abort_wf, "indexing_abort_wf"):
        process_id = start_process("indexing_abort_wf", [{}])

        # The process must really be suspended: `abort_wf` returns the state untouched when it is
        # already complete, which would make the abort below a no-op and this test vacuous.
        process = db.session.get(ProcessTable, process_id)
        assert process.last_status == ProcessStatus.SUSPENDED
        assert _indexed_values(process_id)["process.last_status"] == ProcessStatus.SUSPENDED

        result = abort_process(process, user="tester")

        assert_aborted(result)
        # The suspended index row was overwritten with the abort, so this proves the abort exit
        # was indexed rather than merely observing the earlier suspension.
        assert _indexed_values(process_id)["process.last_status"] == ProcessStatus.ABORTED


def test_timed_out_awaiting_process_is_indexed(generic_subscription_1):
    """The callback-timeout exit is the one Failed path whose state keeps its subscription.

    `fail_awaiting_wf` rebuilds the state from the previous one, unlike a failing step which
    replaces it with an error record. It is also the only exit called from inside another
    workflow's step, so it runs against a live caller session.
    """
    with WorkflowInstanceForTests(indexing_timeout_wf, "indexing_timeout_wf"):
        process_id = start_process("indexing_timeout_wf", [{"subscription_id": generic_subscription_1}])

        assert db.session.get(ProcessTable, process_id).last_status == ProcessStatus.AWAITING_CALLBACK
        _backdate_await_step(process_id, seconds=600)

        fail_awaiting_process(db.session.get(ProcessTable, process_id))

        assert _indexed_values(process_id)["process.last_status"] == ProcessStatus.FAILED
        assert _indexed_values(generic_subscription_1), "the subscription kept in state must be indexed too"


def test_indexing_failure_leaves_the_callers_session_usable():
    """Indexing runs in its own scope, so a failing query cannot poison the session it was called from.

    `fail_awaiting_process` is called from inside a step of the callback-timeout sweep, which keeps
    using its session afterwards; a swallowed indexing error must not leave that session needing a
    rollback nobody issues.
    """
    with WorkflowInstanceForTests(indexing_abort_wf, "indexing_abort_wf"):
        process_id = start_process("indexing_abort_wf", [{}])
        process = db.session.get(ProcessTable, process_id)

        with patch(
            "orchestrator.core.search.indexing.hooks.run_indexing_for_entity",
            side_effect=ProgrammingError("SELECT boom", {}, Exception("boom")),
        ):
            abort_process(process, user="tester")

        # Both of these fail if indexing had run on -- and broken -- the caller's session.
        assert db.session.get(ProcessTable, process_id).last_status == ProcessStatus.ABORTED
        assert db.session.scalars(select(ProcessTable.process_id).limit(1)).all() is not None


def test_workflow_still_referencing_the_deprecated_steps_runs(generic_subscription_1):
    """Downstream step lists that still contain the old refresh steps must keep working untouched."""
    # Spy on the real indexer rather than replacing it: the workflow still indexes for real, and
    # the call count proves the deprecated steps did not index a second time.
    with patch(
        "orchestrator.core.search.indexing.hooks.run_indexing_for_entity",
        wraps=indexing_tasks.run_indexing_for_entity,
    ) as spy:
        with WorkflowInstanceForTests(indexing_legacy_steps_wf, "indexing_legacy_steps_wf"):
            process_id = start_process("indexing_legacy_steps_wf", [{"subscription_id": generic_subscription_1}])

            process = db.session.get(ProcessTable, process_id)
            assert process.last_status == ProcessStatus.COMPLETED
            assert "Refresh subscription search index" in [process_step.name for process_step in process.steps]

            assert _indexed_values(process_id)["process.last_status"] == ProcessStatus.COMPLETED
            assert _indexed_values(generic_subscription_1)

            # Once per entity: the exit hook indexed, the deprecated steps stayed no-ops.
            assert spy.call_count == 2


def test_subscription_in_state_is_indexed(generic_subscription_1):
    with WorkflowInstanceForTests(indexing_subscription_wf, "indexing_subscription_wf"):
        process_id = start_process("indexing_subscription_wf", [{"subscription_id": generic_subscription_1}])

        assert _indexed_values(process_id)["process.last_status"] == ProcessStatus.COMPLETED
        assert _indexed_values(generic_subscription_1), "subscription found in state must be indexed"
