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
from http import HTTPStatus

import pytest
from sqlalchemy import func, select

from orchestrator.core.db import ProcessTable, db
from orchestrator.core.services.processes import create_process
from orchestrator.core.targets import Target
from orchestrator.core.utils.errors import StartPredicateError
from orchestrator.core.workflow import RunPredicateFail, RunPredicatePass, begin, done, step, workflow
from test.unit_tests.config import GRAPHQL_ENDPOINT, GRAPHQL_HEADERS
from test.unit_tests.graphql.mutations.helpers import mutation_authorization
from test.unit_tests.workflows import WorkflowInstanceForTests, assert_complete, run_workflow


def get_start_process_mutation(name: str, payload: dict) -> bytes:
    query = """
mutation StartProcessMutation ($name: String!, $payload: Payload!) {
    startProcess(name: $name, payload: $payload) {
        ... on ProcessCreated {
            id
        }
        ... on MutationError {
            message
            details
        }
    }
}
    """
    return json.dumps(
        {
            "operationName": "StartProcessMutation",
            "query": query,
            "variables": {"name": name, "payload": payload},
        }
    ).encode("utf-8")


# --- Workflow-level tests (via run_workflow) ---


def test_workflow_without_predicate_starts_normally():
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow(target=Target.SYSTEM)
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_no_predicate"):
        result, process, step_log = run_workflow("test_wf_no_predicate", {})
        assert_complete(result)


def test_workflow_with_true_predicate_starts_normally():
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow(target=Target.SYSTEM, run_predicate=lambda ctx: RunPredicatePass())
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_true_predicate"):
        result, process, step_log = run_workflow("test_wf_true_predicate", {})
        assert_complete(result)


def test_workflow_with_false_predicate_raises_error():
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow(
        target=Target.SYSTEM,
        run_predicate=lambda ctx: RunPredicateFail("Start predicate for workflow is not satisfied"),
    )
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_false_predicate"):
        with pytest.raises(StartPredicateError, match="is not satisfied"):
            run_workflow("test_wf_false_predicate", {})


def test_false_predicate_with_reason():
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow(
        target=Target.SYSTEM,
        run_predicate=lambda ctx: RunPredicateFail("Maintenance window is closed"),
    )
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_with_reason"):
        with pytest.raises(StartPredicateError, match="Maintenance window is closed") as exc_info:
            run_workflow("test_wf_with_reason", {})

        assert exc_info.value.workflow_key == "test_wf_with_reason"
        assert exc_info.value.message == "Maintenance window is closed"


def test_false_predicate_message_is_passed_through():
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow(
        target=Target.SYSTEM,
        run_predicate=lambda ctx: RunPredicateFail("Custom failure reason"),
    )
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_message"):
        with pytest.raises(StartPredicateError) as exc_info:
            run_workflow("test_wf_message", {})

        assert exc_info.value.workflow_key == "test_wf_message"
        assert exc_info.value.message == "Custom failure reason"


def test_false_predicate_does_not_create_db_row():
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow(
        target=Target.SYSTEM,
        run_predicate=lambda ctx: RunPredicateFail("Start predicate for workflow is not satisfied"),
    )
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_no_db_row") as wf_table:
        initial_count = db.session.scalar(
            select(func.count()).select_from(ProcessTable).filter(ProcessTable.workflow_id == wf_table.workflow_id)
        )

        with pytest.raises(StartPredicateError):
            create_process("test_wf_no_db_row", user_inputs=[{}])

        final_count = db.session.scalar(
            select(func.count()).select_from(ProcessTable).filter(ProcessTable.workflow_id == wf_table.workflow_id)
        )
        assert initial_count == final_count


# --- REST API tests ---


def test_start_predicate_returns_412_via_rest(test_client):
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow(
        target=Target.SYSTEM,
        run_predicate=lambda ctx: RunPredicateFail("Start predicate for workflow is not satisfied"),
    )
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_blocked"):
        response = test_client.post("/api/processes/test_wf_blocked", json=[{}])
        assert HTTPStatus.PRECONDITION_FAILED == response.status_code
        assert "is not satisfied" in response.json()["detail"]


def test_start_predicate_reason_in_412_response(test_client):
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow(
        target=Target.SYSTEM,
        run_predicate=lambda ctx: RunPredicateFail("System is in read-only mode"),
    )
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_reason_412"):
        response = test_client.post("/api/processes/test_wf_reason_412", json=[{}])
        assert HTTPStatus.PRECONDITION_FAILED == response.status_code
        assert "System is in read-only mode" in response.json()["detail"]


def test_start_predicate_passes_via_rest(test_client):
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow(target=Target.SYSTEM, run_predicate=lambda ctx: RunPredicatePass())
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_allowed"):
        response = test_client.post("/api/processes/test_wf_allowed", json=[{}])
        assert HTTPStatus.CREATED == response.status_code
        assert "id" in response.json()


# --- GraphQL mutation tests ---


def test_start_predicate_returns_mutation_error_via_graphql(test_client_graphql):
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow(
        target=Target.SYSTEM,
        run_predicate=lambda ctx: RunPredicateFail("Start predicate for workflow is not satisfied"),
    )
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_blocked_gql"):
        query = get_start_process_mutation(name="test_wf_blocked_gql", payload={"payload": [{}]})

        with mutation_authorization():
            response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=query, headers=GRAPHQL_HEADERS)

        assert response.status_code == HTTPStatus.OK
        data = response.json()["data"]["startProcess"]
        assert data["message"] == "Start predicate not satisfied"
        assert "is not satisfied" in data["details"]


def test_start_predicate_reason_in_graphql_error(test_client_graphql):
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow(
        target=Target.SYSTEM,
        run_predicate=lambda ctx: RunPredicateFail("Already running"),
    )
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_reason_gql"):
        query = get_start_process_mutation(name="test_wf_reason_gql", payload={"payload": [{}]})

        with mutation_authorization():
            response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=query, headers=GRAPHQL_HEADERS)

        assert response.status_code == HTTPStatus.OK
        data = response.json()["data"]["startProcess"]
        assert data["message"] == "Start predicate not satisfied"
        assert "Already running" in data["details"]


def test_start_predicate_passes_via_graphql(test_client_graphql):
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow(target=Target.SYSTEM, run_predicate=lambda ctx: RunPredicatePass())
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_allowed_gql"):
        query = get_start_process_mutation(name="test_wf_allowed_gql", payload={"payload": [{}]})

        with mutation_authorization():
            response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=query, headers=GRAPHQL_HEADERS)

        assert response.status_code == HTTPStatus.OK
        data = response.json()["data"]["startProcess"]
        assert data.get("id")
