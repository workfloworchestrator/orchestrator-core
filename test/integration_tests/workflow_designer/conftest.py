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

from orchestrator.core.db import ProcessTable, WorkflowTable, db
from orchestrator.core.workflow import ProcessStatus
from orchestrator.core.workflow_designer.definition import StepRef, WorkflowDefinition
from orchestrator.core.workflow_designer.discovery import discover_steps
from orchestrator.core.workflow_designer.forms import FormField
from orchestrator.core.workflow_designer.source import designed_workflows

REPORT = WorkflowDefinition(
    name="designed_note_report",
    description="Store a note and log it",
    form_fields=[
        FormField(name="subscription_id", type="uuid", title="Subscription"),
        FormField(name="note", type="string", title="Note"),
    ],
    steps=[
        StepRef(step_id="orchestrator.core.workflows.modify_note:store_subscription_note"),
        StepRef(step_id="designer:set_value", config={"key": "checked_by", "value": "designer"}),
        StepRef(step_id="designer:log_message", config={"template": "{note} set on {subscription_id} by {checked_by}"}),
    ],
)


@pytest.fixture(scope="session", autouse=True)
def scanned_steps():
    # Validation needs the step scan; product tags only matter for subscription model parameters, unused here.
    discover_steps(product_tags=dict)


@pytest.fixture(autouse=True)
def fresh_designed_workflow_cache():
    """Rows are rolled back after each test, so a later test may reuse a name with a different workflow_id."""
    designed_workflows.invalidate()
    yield
    designed_workflows.invalidate()


def add_process(workflow_name: str, status: ProcessStatus) -> ProcessTable:
    workflow = db.session.scalars(WorkflowTable.select().where(WorkflowTable.name == workflow_name)).one()
    process = ProcessTable(
        workflow_id=workflow.workflow_id, last_status=status, assignee="SYSTEM", is_task=True, created_by="test"
    )
    db.session.add(process)
    db.session.commit()
    return process
