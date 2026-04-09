"""Unit tests for parallel branch support."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from orchestrator.workflow import (
    StepList,
    Waiting,
    _dispatch_worker_branches,
    _exec_parallel_branches,
    begin,
    parallel,
    process_stat_var,
    reconstruct_branch,
    step,
)


@step("Step A")
def _step_a() -> dict:
    return {"a": 1}


@step("Step B")
def _step_b() -> dict:
    return {"b": 2}


# -- reconstruct_branch --


def test_reconstruct_branch_returns_step_list() -> None:
    par_step = parallel("Test group", begin >> _step_a, begin >> _step_b)
    branch = reconstruct_branch(par_step, 0)
    assert len(branch) > 0


def test_reconstruct_branch_index_out_of_range_raises() -> None:
    par_step = parallel("Test group", begin >> _step_a, begin >> _step_b)
    with pytest.raises(IndexError):
        reconstruct_branch(par_step, 5)


def test_reconstruct_branch_non_parallel_step_raises() -> None:
    with pytest.raises(ValueError, match="not a parallel step"):
        reconstruct_branch(_step_a, 0)


# -- executor dispatch --


def test_threadpool_executor_is_default() -> None:
    # Clear any stale process context from previous tests so _exec_parallel_branches
    # runs without DB involvement (no fork step creation).
    token = process_stat_var.set(None)  # type: ignore[arg-type]
    try:
        result = _exec_parallel_branches(
            branches=[StepList([_step_a]), StepList([_step_b])],
            initial_state={},
            name="test",
        )
    finally:
        process_stat_var.reset(token)
    assert result.issuccess()


@pytest.mark.parametrize("is_task", [pytest.param(True, id="task"), pytest.param(False, id="workflow")])
@patch("orchestrator.services.tasks.get_celery_task")
def test_worker_branches_submits_tasks_and_returns_waiting(mock_get_task: MagicMock, is_task: bool) -> None:
    mock_task = MagicMock()
    mock_get_task.return_value = mock_task

    fork_id = uuid4()
    process_id = uuid4()

    result = _dispatch_worker_branches(
        branches=[StepList([_step_a]), StepList([_step_b])],
        initial_state={"x": 1},
        process_id=process_id,
        current_user="test_user",
        fork_step_id=fork_id,
        is_task=is_task,
    )

    assert isinstance(result, Waiting)
    assert result.unwrap()["__parallel_waiting"] is True
    assert result.unwrap()["__fork_step_id"] == str(fork_id)
    assert mock_task.delay.call_count == 2

    # Verify correct task name was requested
    from orchestrator.services.tasks import EXECUTE_PARALLEL_BRANCH, EXECUTE_PARALLEL_BRANCH_WORKFLOW

    expected_task = EXECUTE_PARALLEL_BRANCH if is_task else EXECUTE_PARALLEL_BRANCH_WORKFLOW
    mock_get_task.assert_called_once_with(expected_task)


# -- atomic increment --


@pytest.mark.parametrize(
    "return_val",
    [
        pytest.param(1, id="first-increment"),
        pytest.param(3, id="mid-increment"),
    ],
)
@patch("orchestrator.services.parallel.db")
def test_atomic_increment_completed_returns_count_and_total(mock_db: MagicMock, return_val: int) -> None:
    from orchestrator.services.parallel import _atomic_increment_completed

    fork_step_id = uuid4()
    mock_result = MagicMock()
    mock_result.one.return_value = (return_val, 5)
    mock_db.session.execute.return_value = mock_result

    completed, total = _atomic_increment_completed(fork_step_id)
    assert completed == return_val
    assert total == 5
    mock_db.session.commit.assert_called_once()


@patch("orchestrator.services.parallel.db")
def test_atomic_increment_executes_update_on_process_steps(mock_db: MagicMock) -> None:
    from orchestrator.services.parallel import _atomic_increment_completed

    fork_step_id = uuid4()
    mock_result = MagicMock()
    mock_result.one.return_value = (2, 4)
    mock_db.session.execute.return_value = mock_result

    _atomic_increment_completed(fork_step_id)

    mock_db.session.execute.assert_called_once()
    stmt = mock_db.session.execute.call_args[0][0]
    assert "process_steps" in str(stmt)
