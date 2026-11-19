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
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from orchestrator.core import begin, parallel, step
from orchestrator.core.config.assignee import Assignee
from orchestrator.core.workflow import (
    AwaitingCallback,
    Failed,
    Step,
    StepImportance,
    StepList,
    Success,
    Suspend,
    Waiting,
    _dispatch_worker_branches,
    _iter_parallel_group_names,
    _max_parallel_workers,
    _run_threadpool_branches,
    _warn_about_default_concurrency_budget,
    callback_step,
    conditional,
    done,
    focussteps,
    init,
    make_step_function,
    map_parallel,
    reconstruct_branch,
    step_group,
    workflow,
)
from orchestrator.core.workflow import (
    _worst_status as worst_status,
)
from pydantic_forms.core import FormPage


@pytest.mark.parametrize(
    "pending, max_concurrency, pool_size, max_overflow, max_workers, expected",
    [
        pytest.param(200, None, 60, 10, 5, 5, id="defaults-to-outer-worker-count"),
        pytest.param(200, 200, 60, 10, 5, 9, id="explicit-value-capped-by-shared-connection-budget"),
        pytest.param(3, None, 60, 10, 5, 3, id="does-not-exceed-pending-branches"),
        pytest.param(2, 20, 1, 0, 200, 1, id="small-pool-still-runs-serially"),
    ],
)
def test_max_parallel_workers(pending, max_concurrency, pool_size, max_overflow, max_workers, expected):
    workers = _max_parallel_workers(pending, max_concurrency, pool_size, max_overflow, max_workers)

    assert workers == expected


@pytest.mark.parametrize("max_concurrency", [0, -1])
def test_max_parallel_workers_rejects_non_positive_explicit_value(max_concurrency):
    with pytest.raises(ValueError, match="max_concurrency must be greater than 0"):
        _max_parallel_workers(10, max_concurrency, 60, 10, 5)


@pytest.mark.parametrize(
    "max_concurrency, max_workers",
    [
        pytest.param(200, 5, id="explicit-concurrency-above-budget"),
        pytest.param(None, 18, id="serial-floor-for-large-worker-count"),
    ],
)
def test_max_parallel_workers_warns_once_when_budget_throttles(max_concurrency, max_workers):
    _warn_about_default_concurrency_budget.cache_clear()
    with patch("orchestrator.core.workflow.logger") as mock_logger:
        workers = [
            _max_parallel_workers(200, max_concurrency, 60, 10, max_workers),
            _max_parallel_workers(200, max_concurrency, 60, 10, max_workers),
        ]

    expected_requested = max_concurrency if max_concurrency is not None else max_workers
    expected_budget = 9 if max_workers == 5 else 1
    assert workers == [expected_budget] * 2
    attempted_calls = 2 if max_concurrency is not None else 1
    assert mock_logger.warning.call_count == attempted_calls
    if max_concurrency is None:
        assert _warn_about_default_concurrency_budget.cache_info().hits == 1
    mock_logger.warning.assert_called_with(
        "Reducing parallel branch concurrency to the connection-pool budget",
        requested_concurrency=expected_requested,
        branch_budget=expected_budget,
        connection_pool_capacity=70,
        max_workers=max_workers,
    )


def test_max_parallel_workers_does_not_warn_when_pending_fits_budget():
    _warn_about_default_concurrency_budget.cache_clear()
    with patch("orchestrator.core.workflow.logger") as mock_logger:
        assert _max_parallel_workers(5, 200, 60, 10, 5) == 5
        assert _max_parallel_workers(1, None, 60, 10, 18) == 1

    mock_logger.warning.assert_not_called()


@pytest.mark.parametrize(
    "construct",
    [
        pytest.param(
            lambda: parallel("Parallel", begin >> _step_a, begin >> _step_b, max_concurrency=0), id="parallel"
        ),
        pytest.param(lambda: map_parallel("Map", "items", begin >> _step_a, max_concurrency=-1), id="map-parallel"),
    ],
)
def test_parallel_step_rejects_non_positive_concurrency_at_definition(construct):
    with pytest.raises(ValueError, match="max_concurrency must be greater than 0"):
        construct()


@patch("orchestrator.core.workflow.ThreadPoolExecutor")
@patch("orchestrator.core.workflow.db")
def test_threadpool_rejects_non_positive_concurrency_before_creating_executor(_mock_db, mock_executor):
    with pytest.raises(ValueError, match="max_concurrency must be greater than 0"):
        _run_threadpool_branches(
            branches=[StepList([_step_a]), StepList([_step_b])],
            initial_state={},
            name="test",
            process_id=None,
            fork_step_id=None,
            current_user="",
            max_concurrency=0,
        )

    mock_executor.assert_not_called()


@step("Step A")
def _step_a() -> dict:
    return {"a": 1}


@step("Step B")
def _step_b() -> dict:
    return {"b": 2}


@pytest.mark.parametrize(
    "results, expected_check",
    [
        ([Failed({"error": "boom"})], "isfailed"),
        ([Waiting({"w": 1})], "iswaiting"),
        ([Suspend({"s": 1})], "issuspend"),
        ([AwaitingCallback({"ac": 1})], "isawaitingcallback"),
        ([Success({"a": 1}), Success({"b": 2})], None),
        ([Waiting({"w": 1}), Failed({"error": "x"})], "isfailed"),
        ([Suspend({"s": 1}), Failed({"error": "x"})], "isfailed"),
        ([AwaitingCallback({"ac": 1}), Failed({"error": "x"})], "isfailed"),
        ([Suspend({"s": 1}), Waiting({"w": 1})], "iswaiting"),
        ([AwaitingCallback({"ac": 1}), Waiting({"w": 1})], "iswaiting"),
        ([AwaitingCallback({"ac": 1}), Suspend({"s": 1})], "issuspend"),
        ([Success({"a": 1}), Waiting({"w": 1}), Failed({"error": "x"})], "isfailed"),
        ([Success({"a": 1}), Suspend({"s": 1}), AwaitingCallback({"ac": 1})], "issuspend"),
    ],
    ids=[
        "single-failed",
        "single-waiting",
        "single-suspend",
        "single-awaiting-callback",
        "all-success",
        "waiting-and-failed",
        "suspend-and-failed",
        "awaiting-callback-and-failed",
        "suspend-and-waiting",
        "awaiting-callback-and-waiting",
        "awaiting-callback-and-suspend",
        "three-branches-failed-wins",
        "three-branches-suspend-wins",
    ],
)
def test_worst_status_priority(results: list, expected_check: str | None) -> None:
    worst = worst_status(results)
    if expected_check is None:
        assert worst is None
    else:
        assert worst is not None
        assert getattr(worst, expected_check)()


def test_callback_step_in_parallel_raises() -> None:
    from orchestrator.core.workflow import begin, callback_step, parallel, step

    @step("CB Action")
    def _cb_action() -> dict:
        return {}

    @step("CB Validate")
    def _cb_validate() -> dict:
        return {}

    _test_callback = callback_step("Test callback", _cb_action, _cb_validate)

    @step("Branch A")
    def branch_a() -> dict:
        return {"a": 1}

    with pytest.raises(ValueError, match="callback"):
        # Tests both a StepList and Step
        parallel("Invalid parallel", begin >> branch_a, _test_callback)


# -- reconstruct_branch --


def test_reconstruct_branch_returns_step_list() -> None:
    par_step = parallel("Test group", begin >> _step_a, begin >> _step_b)
    branch = reconstruct_branch(par_step, 0)
    assert len(branch) > 0


def test_reconstruct_branch_returns_the_branch_at_the_index() -> None:
    par_step = parallel("Test group", begin >> _step_a, begin >> _step_b)
    assert par_step.branching is not None
    assert reconstruct_branch(par_step, 1) == par_step.branching.branches[1]


def test_reconstruct_branch_index_out_of_range_raises() -> None:
    par_step = parallel("Test group", begin >> _step_a, begin >> _step_b)
    with pytest.raises(IndexError):
        reconstruct_branch(par_step, 5)


def test_reconstruct_branch_of_a_step_that_does_not_branch_raises() -> None:
    with pytest.raises(ValueError, match="not a parallel step"):
        reconstruct_branch(_step_a, 0)


@pytest.mark.parametrize("branch_index", [0, 1, 7])
def test_reconstruct_branch_of_map_parallel_returns_the_template(branch_index: int) -> None:
    """Every item of a map_parallel runs the same template, whatever the branch index."""
    template = begin >> _step_a
    step_fn = map_parallel("Per item", "items", template)

    assert reconstruct_branch(step_fn, branch_index) == template


def test_steps_without_branching_have_no_branches() -> None:
    """A step that doesn't fan out has no branches and no sub steps."""
    assert _step_a.branching is None
    assert _step_a.sub_steps is None


# -- parallel group names are unique --


def test_duplicate_group_name_at_top_level_raises() -> None:
    """Two parallel blocks with the same name are rejected when the workflow is built."""
    with pytest.raises(ValueError, match=r"Duplicate parallel group name\(s\) \['Same group'\]"):

        @workflow()
        def duplicate_top_level_wf():
            return (
                init
                >> parallel("Same group", begin >> _step_a, begin >> _step_b)
                >> parallel("Same group", begin >> _step_a, begin >> _step_b)
                >> done
            )


def test_duplicate_group_name_nested_in_branch_raises() -> None:
    """A nested parallel block that reuses an outer group name is rejected."""
    with pytest.raises(ValueError, match=r"Duplicate parallel group name\(s\) \['Outer'\]"):

        @workflow()
        def duplicate_nested_wf():
            return (
                init
                >> parallel(
                    "Outer",
                    begin >> _step_a >> parallel("Outer", begin >> _step_a, begin >> _step_b),
                    begin >> _step_b,
                )
                >> done
            )


def test_duplicate_group_name_across_parallel_and_map_parallel_raises() -> None:
    """parallel() and map_parallel() share the group-name namespace of a workflow."""
    with pytest.raises(ValueError, match=r"Duplicate parallel group name\(s\) \['Shared name'\]"):

        @workflow()
        def duplicate_map_parallel_wf():
            return (
                init
                >> parallel("Shared name", begin >> _step_a, begin >> _step_b)
                >> map_parallel("Shared name", "items", begin >> _step_a)
                >> done
            )


def test_duplicate_group_name_inside_map_parallel_template_raises() -> None:
    """A duplicate inside a map_parallel template is found by walking the template."""
    with pytest.raises(ValueError, match=r"Duplicate parallel group name\(s\) \['Repeated'\]"):

        @workflow()
        def duplicate_in_template_wf():
            return (
                init
                >> map_parallel(
                    "Repeated",
                    "items",
                    begin >> parallel("Repeated", begin >> _step_a, begin >> _step_b),
                )
                >> done
            )


def test_duplicate_group_name_reported_once_per_name() -> None:
    """A name used three times is reported once, not once per extra occurrence."""
    with pytest.raises(ValueError, match=r"Duplicate parallel group name\(s\) \['Trio'\]"):

        @workflow()
        def triple_duplicate_wf():
            return (
                init
                >> parallel("Trio", begin >> _step_a, begin >> _step_b)
                >> parallel("Trio", begin >> _step_a, begin >> _step_b)
                >> parallel("Trio", begin >> _step_a, begin >> _step_b)
                >> done
            )


def test_distinct_group_names_at_any_depth_are_allowed() -> None:
    """Distinct group names, nested or not, are accepted; the tree walk yields them in order."""

    @workflow()
    def distinct_names_wf():
        return (
            init
            >> parallel(
                "Outer",
                begin >> _step_a >> parallel("Inner", begin >> _step_a, begin >> _step_b),
                begin >> _step_b,
            )
            >> map_parallel("Per item", "items", begin >> _step_a)
            >> done
        )

    assert list(_iter_parallel_group_names(distinct_names_wf.steps)) == ["Outer", "Inner", "Per item"]


def test_workflow_without_parallel_steps_is_allowed() -> None:
    """A workflow without parallel steps has no group names to check."""

    @workflow()
    def no_parallel_wf():
        return init >> _step_a >> done

    assert list(_iter_parallel_group_names(no_parallel_wf.steps)) == []


# -- executor dispatch --


# TODO move this when _dispatch_worker_branches itself is moved
@pytest.mark.parametrize("is_task", [pytest.param(True, id="task"), pytest.param(False, id="workflow")])
@patch("orchestrator.core.services.parallel._succeeded_branch_indices", return_value=set())
@patch("orchestrator.core.services.tasks.get_celery_task")
def test_worker_branches_submits_tasks_and_returns_waiting(
    mock_get_task: MagicMock, _mock_succeeded: MagicMock, is_task: bool
) -> None:
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
    from orchestrator.core.services.tasks import (
        EXECUTE_PARALLEL_BRANCH_TASK,
        EXECUTE_PARALLEL_BRANCH_WORKFLOW_TASK,
    )

    expected_task = EXECUTE_PARALLEL_BRANCH_TASK if is_task else EXECUTE_PARALLEL_BRANCH_WORKFLOW_TASK
    mock_get_task.assert_called_once_with(expected_task)


# -- typed step metadata --


class _Form(FormPage):
    answer: int


async def _retry_allow(_context) -> bool:
    return True


async def _resume_allow(_context) -> bool:
    return True


def _step_attributes(step_fn: Step) -> tuple:
    """Everything a rewrap has to copy, in a form that compares by identity for the callables."""
    return (
        step_fn.name,
        step_fn.form,
        step_fn.assignee,
        step_fn.resume_auth_callback,
        step_fn.retry_auth_callback,
        step_fn.importance,
        step_fn.branching,
        step_fn.sub_steps,
        step_fn.is_callback_step,
    )


@pytest.mark.parametrize(
    "rewrap",
    [
        lambda step_fn: conditional(lambda _state: True)(step_fn)[0],
        lambda step_fn: focussteps("sub")(step_fn)[0],
    ],
    ids=["conditional", "focussteps"],
)
@pytest.mark.parametrize(
    "step_fn_factory",
    [
        pytest.param(
            lambda: make_step_function(
                lambda state: Success(state),
                "Plain",
                _Form,
                Assignee.NOC,
                resume_auth_callback=_resume_allow,
                retry_auth_callback=_retry_allow,
                importance=StepImportance.HIGH,
            ),
            id="plain-step",
        ),
        pytest.param(
            lambda: parallel("Wrapped group", begin >> _step_a, begin >> _step_b),
            id="parallel-step",
        ),
        pytest.param(
            lambda: map_parallel("Wrapped map", "items", begin >> _step_a),
            id="map-parallel-step",
        ),
        pytest.param(
            lambda: step_group("Wrapped group", begin >> _step_a),
            id="step-group",
        ),
    ],
)
def test_wrapping_a_step_copies_every_step_attribute(rewrap, step_fn_factory) -> None:
    """Conditional and steplens (and so focussteps) keep all Step attributes, including both auth callbacks."""
    step_fn = step_fn_factory()

    wrapped = rewrap(step_fn)

    assert _step_attributes(wrapped) == _step_attributes(step_fn)


def test_step_group_and_callback_step_expose_their_sub_steps() -> None:
    """step_group stores its steps on the Step, so the tree walk reaches them; callback_step is one too."""
    group = step_group("Group", begin >> _step_a)
    # The group's own Enter step and the given steps, followed by its Exit step.
    assert group.sub_steps is not None
    assert [s.name for s in group.sub_steps] == ["Group - Enter", "Step A", "Group - Exit"]
    assert group.branching is None
    assert not group.is_callback_step

    cb = callback_step("Callback", action_step=_step_a, validate_step=_step_b)
    assert cb.is_callback_step
    assert cb.sub_steps is not None
    assert [s.name for s in cb.sub_steps] == [
        "Callback - Enter",
        "Callback - Create endpoint",
        "Step A",
        "Callback - Await callback",
        "Step B",
        "Callback - Cleanup callback step",
        "Callback - Exit",
    ]


def test_focussteps_keeps_the_retry_auth_callback() -> None:
    """Focussteps zooms its input state, but the step it represents keeps its authorization callbacks."""
    step_fn = make_step_function(
        lambda state: Success(state),
        "Authorized",
        retry_auth_callback=_retry_allow,
        resume_auth_callback=_resume_allow,
    )

    wrapped = focussteps("sub")(step_fn)[0]

    assert wrapped.retry_auth_callback is _retry_allow
    assert wrapped.resume_auth_callback is _resume_allow
