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

from orchestrator.core.services.subscriptions import get_subscription
from orchestrator.core.utils.functional import orig
from orchestrator.core.workflow_designer.definition import StepRef, WorkflowDefinition
from orchestrator.core.workflow_designer.forms import FormField
from orchestrator.core.workflow_designer.service import create_workflow
from orchestrator.core.workflows.tasks import validate_products
from test.integration_tests.workflow_designer.conftest import REPORT
from test.integration_tests.workflows import (
    assert_complete,
    assert_suspended,
    extract_state,
    resume_workflow,
    run_workflow,
)

CONFIRM = WorkflowDefinition(
    name="designed_confirm",
    description="Confirm, then log",
    form_fields=[FormField(name="note", type="string")],
    steps=[
        StepRef(step_id="designer:confirm", config={"message": "Log the note?"}),
        StepRef(step_id="designer:log_message", config={"template": "{note} (confirmed: {confirmed})"}),
    ],
)


@pytest.mark.workflow
def test_designed_workflow_runs_code_steps_and_helpers(responses, generic_subscription_1):
    create_workflow(REPORT, user="jane")

    result, _, step_log = run_workflow(REPORT.name, [{"subscription_id": generic_subscription_1, "note": "checked"}])

    assert_complete(result)
    state = extract_state(result)
    assert [step.name for step, _ in step_log] == ["Start", "Store note", "Set checked_by", "Log message", "Done"]
    assert state["designer_log"] == [f"checked set on {generic_subscription_1} by designer"]
    assert get_subscription(generic_subscription_1).note == "checked"


@pytest.mark.workflow
def test_designed_workflow_pauses_for_confirmation(responses):
    create_workflow(CONFIRM, user="jane")

    result, process, step_log = run_workflow(CONFIRM.name, [{"note": "hello"}])
    assert_suspended(result)

    result, step_log = resume_workflow(process, step_log, [{"accept_designer_confirmation": "ACCEPTED"}])

    assert_complete(result)
    assert extract_state(result)["designer_log"] == ["hello (confirmed: True)"]


def test_designed_tasks_pass_the_workflow_registration_check():
    create_workflow(REPORT, user="jane")

    assert orig(validate_products.check_all_workflows_are_in_db)() == {"check_all_workflows_are_in_db": True}
