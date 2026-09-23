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

"""Routing tests for CELERY_TARGET_QUEUES.

Workflows whose target appears in the mapping must be enqueued on the mapped
queue (start and resume alike); everything else must keep the default
task_routes routing, i.e. the ``queue`` option must be absent entirely
(passing ``queue=None`` would be a routing regression).
"""

from unittest import mock
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from orchestrator.core import app_settings
from orchestrator.core.db.models import ProcessTable
from orchestrator.core.services.executors.celery import (
    _celery_resume_process,
    _celery_start_process,
    _resolve_queue,
)
from orchestrator.core.services.processes import SYSTEM_USER
from orchestrator.core.services.tasks import NEW_TASK, NEW_WORKFLOW, RESUME_TASK, RESUME_WORKFLOW
from orchestrator.core.targets import Target
from orchestrator.core.workflow import ProcessStatus

RECONCILE_ONLY = {Target.RECONCILE: "reconcile"}
RECONCILE_AND_VALIDATE = {Target.RECONCILE: "reconcile", Target.VALIDATE: "validate"}

ROUTING_MATRIX = [
    pytest.param({}, Target.RECONCILE, False, None, id="empty-mapping-reconcile-default-queue"),
    pytest.param(RECONCILE_ONLY, Target.RECONCILE, False, "reconcile", id="mapped-target-routed"),
    pytest.param(RECONCILE_ONLY, Target.CREATE, False, None, id="unmapped-target-default-queue"),
    pytest.param(RECONCILE_ONLY, Target.RECONCILE, True, "reconcile", id="mapped-target-is-task-routed"),
    pytest.param(RECONCILE_AND_VALIDATE, Target.VALIDATE, True, "validate", id="second-mapping-entry-routed"),
]


def assert_enqueued_once(trigger_task, expected_args, expected_queue):
    """The unmapped case must produce no queue option at all, not queue=None."""
    if expected_queue is None:
        trigger_task.apply_async.assert_called_once_with(expected_args)
    else:
        trigger_task.apply_async.assert_called_once_with(expected_args, queue=expected_queue)


@pytest.mark.parametrize("mapping,target,is_task,expected_queue", ROUTING_MATRIX)
@mock.patch("orchestrator.core.services.tasks.get_celery_task")
@mock.patch("orchestrator.core.services.executors.celery.get_workflow_by_name")
@mock.patch("orchestrator.core.services.executors.celery.db")
def test_celery_start_process_routing(
    mock_db, mock_get_workflow_by_name, mock_get_celery_task, mapping, target, is_task, expected_queue
):
    wf_table = MagicMock()
    wf_table.is_task = is_task
    wf_table.target = str(target)
    mock_get_workflow_by_name.return_value = wf_table

    pstat = MagicMock()
    trigger_task = MagicMock()
    trigger_task.apply_async.return_value.get.return_value = uuid4()
    mock_get_celery_task.return_value = trigger_task

    with mock.patch.object(app_settings, "CELERY_TARGET_QUEUES", mapping):
        process_id = _celery_start_process(pstat)

    assert process_id == pstat.process_id
    # Queue overrides never change the task name: queue = where, task name = what.
    mock_get_celery_task.assert_called_once_with(NEW_TASK if is_task else NEW_WORKFLOW)
    assert_enqueued_once(trigger_task, (pstat.process_id, SYSTEM_USER), expected_queue)


@pytest.mark.parametrize("mapping,target,is_task,expected_queue", ROUTING_MATRIX)
@mock.patch("orchestrator.core.services.tasks.get_celery_task")
@mock.patch("orchestrator.core.services.executors.celery.db")
def test_celery_resume_process_routing(mock_db, mock_get_celery_task, mapping, target, is_task, expected_queue):
    process = MagicMock(spec=ProcessTable)
    process.last_status = ProcessStatus.FAILED
    process.workflow.is_task = is_task
    process.workflow.target = str(target)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = process
    mock_db.session.execute.return_value = mock_result

    trigger_task = MagicMock()
    trigger_task.apply_async.return_value.get.return_value = uuid4()
    mock_get_celery_task.return_value = trigger_task

    with mock.patch.object(app_settings, "CELERY_TARGET_QUEUES", mapping):
        process_id = _celery_resume_process(process, user="testuser")

    assert process_id == process.process_id
    mock_get_celery_task.assert_called_once_with(RESUME_TASK if is_task else RESUME_WORKFLOW)
    assert_enqueued_once(trigger_task, (process.process_id, "testuser"), expected_queue)


@pytest.mark.parametrize(
    "mapping,target,expected_queue",
    [
        pytest.param({}, Target.RECONCILE, None, id="empty-mapping"),
        pytest.param(RECONCILE_ONLY, Target.RECONCILE, "reconcile", id="mapped"),
        pytest.param(RECONCILE_ONLY, Target.MODIFY, None, id="unmapped"),
    ],
)
def test_resolve_queue(mapping, target, expected_queue):
    workflow = MagicMock()
    workflow.target = str(target)

    with mock.patch.object(app_settings, "CELERY_TARGET_QUEUES", mapping):
        assert _resolve_queue(workflow) == expected_queue


def test_resolve_queue_corrupt_target_fails_loudly():
    workflow = MagicMock()
    workflow.target = "NOT_A_TARGET"

    with mock.patch.object(app_settings, "CELERY_TARGET_QUEUES", RECONCILE_ONLY), pytest.raises(ValueError):
        _resolve_queue(workflow)
