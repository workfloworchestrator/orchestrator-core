from uuid import uuid4

import pytest

from orchestrator.db import InputStateTable, ProcessStepTable, ProcessSubscriptionTable, ProcessTable, db
from orchestrator.services.input_state import retrieve_input_state, store_input_state
from orchestrator.workflow import ProcessStatus, StepStatus


@pytest.fixture
def completed_process(test_workflow, generic_subscription_1):
    process_id = uuid4()
    process = ProcessTable(
        process_id=process_id, workflow_id=test_workflow.workflow_id, last_status=ProcessStatus.COMPLETED
    )
    init_step = ProcessStepTable(process_id=process_id, name="Start", status=StepStatus.SUCCESS, state={})
    insert_step = ProcessStepTable(
        process_id=process_id,
        name="Insert UUID in state",
        status=StepStatus.SUCCESS,
        state={"subscription_id": generic_subscription_1},
    )
    check_step = ProcessStepTable(
        process_id=process_id,
        name="Test that it is a string now",
        status=StepStatus.SUCCESS,
        state={"subscription_id": generic_subscription_1},
    )
    step = ProcessStepTable(
        process_id=process_id,
        name="Modify",
        status=StepStatus.SUCCESS,
        state={"subscription_id": generic_subscription_1},
    )

    process_subscription = ProcessSubscriptionTable(process_id=process_id, subscription_id=generic_subscription_1)
    input_state = InputStateTable(process_id=process_id, input_state={"key": "value"}, input_type="initial_state")

    db.session.add(process)
    db.session.add(init_step)
    db.session.add(insert_step)
    db.session.add(check_step)
    db.session.add(step)
    db.session.add(process_subscription)
    db.session.add(input_state)
    db.session.commit()

    return process_id, input_state


def test_retrieve_input_state(completed_process):
    process_id, input_state = completed_process
    retrieved_state = retrieve_input_state(process_id, "initial_state")
    assert retrieved_state == input_state


def test_store_input_state(completed_process):
    process_id, input_state = completed_process
    store_input_state(process_id, input_state.input_state, "user_input")

    states = InputStateTable.query.all()
    assert len(states) == 2
