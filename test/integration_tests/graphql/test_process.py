# Copyright 2022-2026 SURF, ESnet, GÉANT.
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
from http import HTTPStatus
from unittest import mock
from uuid import uuid4

import pytest

from orchestrator.core.config.assignee import Assignee
from orchestrator.core.db import ProcessStepTable, ProcessTable, db
from orchestrator.core.forms import FormPage
from orchestrator.core.targets import Target
from orchestrator.core.utils.auth import AuthContext
from orchestrator.core.workflow import ProcessStatus, StepStatus, done, init, inputstep, workflow
from test.integration_tests.config import GRAPHQL_ENDPOINT
from test.integration_tests.workflows import WorkflowInstanceForTests


def build_simple_query(process_id):
    q = """
        query ProcessQuery($processId: UUID!) {
            process(processId: $processId) {
                processId
                userPermissions {
                    retryAllowed
                    resumeAllowed
                }
            }
        }
        """
    return json.dumps(
        {
            "operationName": "ProcessQuery",
            "query": q,
            "variables": {
                "processId": str(process_id),
            },
        }
    ).encode("utf-8")


def test_process(test_client_graphql, mocked_processes):
    process_id = mocked_processes[0]
    test_query = build_simple_query(process_id)

    response = test_client_graphql.post(
        GRAPHQL_ENDPOINT, content=test_query, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "data": {
            "process": {"processId": str(process_id), "userPermissions": {"resumeAllowed": True, "retryAllowed": True}}
        }
    }


@mock.patch("orchestrator.core.graphql.schemas.process.get_workflow")
def test_process_is_allowed_with_historic_workflow_only_left_in_db(
    mock_get_workflow, test_client_graphql, mocked_processes, test_workflow_soft_deleted
):
    mock_get_workflow.return_value = None
    process_id = mocked_processes[0]
    test_query = build_simple_query(process_id)

    response = test_client_graphql.post(
        GRAPHQL_ENDPOINT, content=test_query, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "data": {
            "process": {
                "processId": str(process_id),
                "userPermissions": {"resumeAllowed": False, "retryAllowed": False},
            }
        }
    }


@pytest.fixture
def process_suspended_on_resume_only_step():
    async def resume_only(context: AuthContext) -> bool:
        return context.action == "resume_workflow"

    class ConfirmForm(FormPage):
        confirm: bool

    @inputstep("resume_only", assignee=Assignee.SYSTEM, resume_auth_callback=resume_only)
    def resume_only_step(state):
        user_input = yield ConfirmForm
        return user_input.model_dump()

    @workflow(target=Target.CREATE)
    def resume_only_workflow():
        return init >> resume_only_step >> done

    with WorkflowInstanceForTests(resume_only_workflow, "resume_only_workflow") as wf:
        process_id = uuid4()
        db.session.add(
            ProcessTable(
                process_id=process_id,
                workflow_id=wf.workflow_id,
                last_status=ProcessStatus.SUSPENDED,
                last_step="Start",
            )
        )
        db.session.add(ProcessStepTable(process_id=process_id, name="Start", status=StepStatus.SUCCESS, state={}))
        db.session.commit()
        yield process_id


def test_process_user_permissions_use_matching_action(test_client_graphql, process_suspended_on_resume_only_step):
    """The resume callback gets the resume context and the retry callback the retry context."""
    response = test_client_graphql.post(
        GRAPHQL_ENDPOINT,
        content=build_simple_query(process_suspended_on_resume_only_step),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()["data"]["process"]["userPermissions"] == {"resumeAllowed": True, "retryAllowed": False}
