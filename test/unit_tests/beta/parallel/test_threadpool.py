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

"""Unit tests for the thread pool executor of the beta parallel steps.

These cover the branch concurrency budget, which is computed from the synchronous connection pool of ``db.engine``
and ``MAX_WORKERS``; nothing here touches a real database.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy.pool import NullPool, QueuePool

from orchestrator.core.beta.parallel.threadpool import (
    _max_parallel_workers,
    _run_threadpool_branches,
    _warn_about_default_concurrency_budget,
)
from orchestrator.core.settings import app_settings
from orchestrator.core.workflow import StepList, step


@step("Step A")
def _step_a() -> dict:
    return {"a": 1}


@step("Step B")
def _step_b() -> dict:
    return {"b": 2}


class _EngineWithPool:
    """Stand-in for ``db.engine`` that only exposes the connection pool ``_max_parallel_workers`` reads."""

    def __init__(self, pool) -> None:
        self.pool = pool


class _DbWithPool:
    """Stand-in for the ``db`` object with a given ``engine.pool``."""

    def __init__(self, pool) -> None:
        self.engine = _EngineWithPool(pool)


def _queue_pool(pool_size: int, max_overflow: int) -> QueuePool:
    """A real ``QueuePool`` that connects only on checkout, so tests never open a connection."""

    def connect_only_on_checkout() -> Any:
        raise AssertionError("the test pool must not open a connection")

    return QueuePool(connect_only_on_checkout, pool_size=pool_size, max_overflow=max_overflow)


@contextmanager
def _connection_pool(pool, max_workers: int) -> Iterator[None]:
    """Make ``_max_parallel_workers`` read ``pool`` as the engine pool and ``max_workers`` as ``MAX_WORKERS``."""
    with (
        patch("orchestrator.core.beta.parallel.threadpool.db", _DbWithPool(pool)),
        patch.object(app_settings, "MAX_WORKERS", max_workers),
    ):
        yield


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
    with _connection_pool(_queue_pool(pool_size, max_overflow), max_workers):
        # when
        workers = _max_parallel_workers(pending, max_concurrency)

    # then
    assert workers == expected


def test_max_parallel_workers_falls_back_to_engine_arguments_for_a_non_queue_pool():
    """A pool that has no size or overflow of its own (``NullPool``) uses the engine arguments instead."""
    with _connection_pool(NullPool(lambda: None), max_workers=5):
        # when
        workers = _max_parallel_workers(200, 200)

    # then
    # ENGINE_ARGUMENTS: pool_size 60, no max_overflow -> capacity 60, reserve 15, (60 - 15) // 5 - 1 == 8
    assert workers == 8


@pytest.mark.parametrize("max_concurrency", [0, -1])
def test_max_parallel_workers_rejects_non_positive_explicit_value(max_concurrency):
    with pytest.raises(ValueError, match="max_concurrency must be greater than 0"):
        _max_parallel_workers(10, max_concurrency)


@pytest.mark.parametrize(
    "max_concurrency, max_workers",
    [
        pytest.param(200, 5, id="explicit-concurrency-above-budget"),
        pytest.param(None, 18, id="serial-floor-for-large-worker-count"),
    ],
)
def test_max_parallel_workers_warns_once_when_budget_throttles(max_concurrency, max_workers):
    # given
    _warn_about_default_concurrency_budget.cache_clear()

    # when
    with (
        _connection_pool(_queue_pool(60, 10), max_workers),
        patch("orchestrator.core.beta.parallel.threadpool.logger") as mock_logger,
    ):
        workers = [
            _max_parallel_workers(200, max_concurrency),
            _max_parallel_workers(200, max_concurrency),
        ]

    # then
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
    with (
        _connection_pool(_queue_pool(60, 10), max_workers=5),
        patch("orchestrator.core.beta.parallel.threadpool.logger") as mock_logger,
    ):
        # when
        assert _max_parallel_workers(5, 200) == 5

    # then
    mock_logger.warning.assert_not_called()

    with (
        _connection_pool(_queue_pool(60, 10), max_workers=18),
        patch("orchestrator.core.beta.parallel.threadpool.logger") as mock_logger,
    ):
        # when
        assert _max_parallel_workers(1, None) == 1

    # then
    mock_logger.warning.assert_not_called()


@patch("orchestrator.core.beta.parallel.threadpool.ThreadPoolExecutor")
@patch("orchestrator.core.beta.parallel.threadpool.db")
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
