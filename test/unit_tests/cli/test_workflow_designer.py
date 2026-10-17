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

import json
from unittest import mock

from typer.testing import CliRunner

from orchestrator.core.cli import workflow_designer
from orchestrator.core.workflow_designer.definition import WorkflowDefinition
from orchestrator.core.workflow_designer.service import StoredWorkflow

runner = CliRunner()


def test_scan_steps_json_filters():
    with mock.patch("orchestrator.core.workflow_designer.discovery.product_tags_by_name", dict):
        result = runner.invoke(
            workflow_designer.app, ["scan-steps", "--json", "--usable-only", "--filter", "store_subscription_note"]
        )

    assert result.exit_code == 0, result.output
    # Log lines of the scan may share stdout with the JSON, depending on how logging was configured.
    steps = json.loads(result.output.strip().splitlines()[-1])
    assert [step["id"] for step in steps] == ["orchestrator.core.workflows.modify_note:store_subscription_note"]
    assert [step_input["name"] for step_input in steps[0]["inputs"]] == ["subscription_id", "note"]


def test_scan_steps_text_lists_helpers():
    result = runner.invoke(workflow_designer.app, ["scan-steps", "--filter", "designer:"])

    assert result.exit_code == 0, result.output
    assert "designer:log_message" in result.output
    assert result.output.rstrip().endswith("4 steps")


def test_list_workflows():
    stored = StoredWorkflow(
        definition=WorkflowDefinition(
            name="designed_note",
            description="d",
            steps=[{"step_id": "orchestrator.core.workflows.modify_note:store_subscription_note", "config": {}}],
        ),
        version=3,
        created_by=None,
        process_count=2,
    )
    with (
        mock.patch("orchestrator.core.workflow_designer.service.list_workflows", return_value=[stored]),
        mock.patch("orchestrator.core.db.db.database_scope"),
    ):
        result = runner.invoke(workflow_designer.app, ["list-workflows"])

    assert result.exit_code == 0, result.output
    assert "designed_note (v3, 2 processes): store_subscription_note" in result.output
