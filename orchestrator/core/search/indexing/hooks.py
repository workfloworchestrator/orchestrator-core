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

"""Indexing hook invoked when a process exits.

Replaces the former `refresh_subscription_search_index` / `refresh_process_search_index`
workflow steps, so that indexing also happens for failed, aborted and suspended processes.
"""

from collections.abc import Iterable
from itertools import chain
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.indexing.tasks import run_indexing_for_entity
from orchestrator.core.settings import llm_settings

if TYPE_CHECKING:
    from orchestrator.core.workflow import Process as WFProcess

logger = structlog.get_logger(__name__)

SUBSCRIPTION_STATE_KEYS: tuple[str, ...] = ("subscription", "subscription_id", "subscriptions", "subscription_ids")


def _extract_ids(value: object) -> Iterable[str]:
    """Return subscription ids found in a single state value."""
    match value:
        case UUID():
            return (str(value),)
        case str():
            return (value,)
        case {"subscription_id": subscription_id}:
            return _extract_ids(subscription_id)
        case list() | tuple() | set():
            return chain.from_iterable(map(_extract_ids, value))
        case _ if (subscription_id := getattr(value, "subscription_id", None)) is not None:
            return _extract_ids(subscription_id)
        case _:
            return ()


def extract_subscription_ids(state: object) -> set[str]:
    """Collect unique subscription ids from a workflow's final state.

    Args:
        state: The unwrapped process state. Anything that is not a dict yields an empty set,
            because suspended/waiting processes may carry an error structure instead of a state.

    Returns:
        Deduplicated subscription ids as strings.
    """
    if not isinstance(state, dict):
        return set()

    values = (state.get(key) for key in SUBSCRIPTION_STATE_KEYS)
    return set(chain.from_iterable(map(_extract_ids, values)))


def index_process_and_subscriptions(process_id: UUID, result: "WFProcess") -> None:
    """Index a process and every subscription referenced by its final state.

    Called whenever a process exits: completed, failed, aborted, suspended or awaiting callback.
    Runs after the process' final status has been committed, so the indexed record carries the
    real terminal status.

    Args:
        process_id: The process to index.
        result: Final process value; `unwrap()` provides the state to scan for subscriptions.

    Raises:
        Exception: Only when `llm_settings.SEARCH_INDEXING_STRICT` is True. Otherwise failures
            are logged and swallowed so indexing can never break a process.
    """
    try:
        run_indexing_for_entity(EntityType.PROCESS, str(process_id))
        for subscription_id in extract_subscription_ids(result.unwrap()):
            run_indexing_for_entity(EntityType.SUBSCRIPTION, subscription_id)
    except Exception as ex:
        if llm_settings.SEARCH_INDEXING_STRICT:
            raise
        logger.warning("Failed to index process and subscriptions", process_id=str(process_id), error=str(ex))
