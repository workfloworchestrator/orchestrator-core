import json
from http import HTTPStatus

import pytest
from sqlalchemy import func, select

from orchestrator.db import ProcessTable, db
from orchestrator.services.processes import create_process
from orchestrator.targets import Target
from orchestrator.utils.errors import StartPredicateError
from orchestrator.workflow import begin, done, step, workflow
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

    @workflow("Test workflow without predicate", target=Target.SYSTEM)
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_no_predicate"):
        result, process, step_log = run_workflow("test_wf_no_predicate", {})
        assert_complete(result)


def test_workflow_with_true_predicate_starts_normally():
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow("Test workflow with passing predicate", target=Target.SYSTEM, run_predicate=lambda: True)
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_true_predicate"):
        result, process, step_log = run_workflow("test_wf_true_predicate", {})
        assert_complete(result)


def test_workflow_with_false_predicate_raises_error():
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow("Test workflow with failing predicate", target=Target.SYSTEM, run_predicate=lambda: False)
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_false_predicate"):
        with pytest.raises(StartPredicateError, match="test_wf_false_predicate"):
            run_workflow("test_wf_false_predicate", {})


def test_false_predicate_does_not_create_db_row():
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow("Test workflow no db row", target=Target.SYSTEM, run_predicate=lambda: False)
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

    @workflow("Test workflow blocked", target=Target.SYSTEM, run_predicate=lambda: False)
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_blocked"):
        response = test_client.post("/api/processes/test_wf_blocked", json=[{}])
        assert HTTPStatus.PRECONDITION_FAILED == response.status_code
        assert "test_wf_blocked" in response.json()["detail"]


def test_start_predicate_passes_via_rest(test_client):
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow("Test workflow allowed", target=Target.SYSTEM, run_predicate=lambda: True)
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_allowed"):
        response = test_client.post("/api/processes/test_wf_allowed", json=[{}])
        assert HTTPStatus.CREATED == response.status_code
        assert "id" in response.json()


# --- GraphQL mutation tests ---


def test_start_predicate_returns_mutation_error_via_graphql(httpx_mock, test_client):
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow("Test workflow blocked gql", target=Target.SYSTEM, run_predicate=lambda: False)
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_blocked_gql"):
        query = get_start_process_mutation(name="test_wf_blocked_gql", payload={"payload": [{}]})

        with mutation_authorization():
            response = test_client.post(GRAPHQL_ENDPOINT, content=query, headers=GRAPHQL_HEADERS)

        assert response.status_code == HTTPStatus.OK
        data = response.json()["data"]["startProcess"]
        assert data["message"] == "Start predicate not satisfied"
        assert "test_wf_blocked_gql" in data["details"]


def test_start_predicate_passes_via_graphql(httpx_mock, test_client):
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow("Test workflow allowed gql", target=Target.SYSTEM, run_predicate=lambda: True)
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_allowed_gql"):
        query = get_start_process_mutation(name="test_wf_allowed_gql", payload={"payload": [{}]})

        with mutation_authorization():
            response = test_client.post(GRAPHQL_ENDPOINT, content=query, headers=GRAPHQL_HEADERS)

        assert response.status_code == HTTPStatus.OK
        data = response.json()["data"]["startProcess"]
        assert data.get("id")
