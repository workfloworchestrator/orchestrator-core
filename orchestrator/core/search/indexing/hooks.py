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
from more_itertools import partition
from sqlalchemy import select

from orchestrator.core.db import ProcessSubscriptionTable, db
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.core.validators import is_uuid
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


def linked_subscription_ids(process_id: UUID) -> set[str]:
    """Return the subscription ids linked to a process in the `processes_subscriptions` table.

    For workflows started on an existing subscription (modify, validate, reconcile, terminate),
    `create_process` writes the link before any step runs. Create workflows have no subscription id
    at start; they are linked once `SubscriptionModel.from_product_id()` creates the subscription.
    Tasks are never linked.

    Unlike the final state, the link survives a step failure: a raising step replaces the whole state
    with an error record, dropping every subscription the workflow had already modified (e.g. set out
    of sync).

    Args:
        process_id: The process whose linked subscriptions to look up.

    Returns:
        Linked subscription ids as strings.
    """
    stmt = select(ProcessSubscriptionTable.subscription_id).where(ProcessSubscriptionTable.process_id == process_id)
    return set(map(str, db.session.scalars(stmt)))


def _indexable_subscription_ids(candidates: Iterable[str], process_id: UUID) -> Iterable[str]:
    """Keep the candidates that are real subscription ids, logging the ones dropped.

    A candidate that is not a UUID is a state key collision (something non-subscription stored
    under a subscription key), not an id. Indexing it would raise, so it is dropped -- but never
    silently: without a trace, a future change to how subscriptions are held in state would stop
    subscription indexing with no exception, no log and no failing test.

    Args:
        candidates: Subscription id candidates read out of the process state.
        process_id: The process being indexed, for log context.

    Returns:
        The candidates that can be indexed.
    """
    skipped, indexable = partition(is_uuid, candidates)
    for candidate in skipped:
        logger.debug("Skipping non-UUID subscription candidate", candidate=candidate, process_id=str(process_id))
    return indexable


def _index_entity(entity_type: EntityType, entity_id: str, process_id: UUID) -> None:
    """Index a single entity, isolated from every other entity indexed for the same process exit.

    Args:
        entity_type: The kind of entity to index.
        entity_id: The entity's id.
        process_id: The process this entity was indexed on behalf of, for log context.

    Raises:
        Exception: Only when `llm_settings.SEARCH_INDEXING_STRICT` is True. Otherwise failures
            are logged and swallowed so one bad entity never blocks the rest, or the process.
    """
    try:
        run_indexing_for_entity(entity_type, entity_id)
    except Exception as ex:
        if llm_settings.SEARCH_INDEXING_STRICT:
            raise
        logger.warning(
            "Failed to index entity",
            entity_type=entity_type,
            entity_id=entity_id,
            process_id=str(process_id),
            error=str(ex),
        )


def _safe_linked_subscription_ids(process_id: UUID) -> set[str]:
    """Look up the linked subscription ids, isolated so a failure cannot block the state-derived ones.

    The query runs in a savepoint: a failed statement aborts the surrounding transaction, which
    would otherwise make every indexing query after it fail too.

    Args:
        process_id: The process whose linked subscriptions to look up.

    Returns:
        Linked subscription ids as strings, or an empty set when the lookup fails.

    Raises:
        Exception: Only when `llm_settings.SEARCH_INDEXING_STRICT` is True.
    """
    try:
        with db.session.begin_nested():
            return linked_subscription_ids(process_id)
    except Exception as ex:
        if llm_settings.SEARCH_INDEXING_STRICT:
            raise
        logger.warning("Failed to look up linked subscriptions", process_id=str(process_id), error=str(ex))
        return set()


def index_process_and_subscriptions(process_id: UUID, result: "WFProcess") -> None:
    """Index a process and every subscription referenced by its final state or linked to it.

    Called whenever a process exits: completed, failed, aborted, suspended or awaiting callback.
    Runs after the process' final status has been committed, so the indexed record carries the
    real terminal status. Subscription ids come from two sources, because neither alone suffices:
    - The result state.
      - Empty when a step raises: the error record replaces the state.
    - The `processes_subscriptions` link table.
      - Only knows the subscription a workflow was started for.

    The process and each subscription are indexed independently: a failure indexing one entity
    never prevents indexing the others, a failed link table lookup never prevents indexing the
    subscriptions found in the state, and a state value that merely looks like a subscription id
    (e.g. an opaque human-readable label) is skipped rather than raised on.

    Args:
        process_id: The process to index.
        result: Final process value; `unwrap()` provides the state to scan for subscriptions.

    Raises:
        Exception: Only when `llm_settings.SEARCH_INDEXING_STRICT` is True, and then only for the
            entity that actually failed — other entities are still attempted first.
    """
    _index_entity(EntityType.PROCESS, str(process_id), process_id)

    subscription_ids = extract_subscription_ids(result.unwrap()) | _safe_linked_subscription_ids(process_id)
    for subscription_id in _indexable_subscription_ids(subscription_ids, process_id):
        _index_entity(EntityType.SUBSCRIPTION, subscription_id, process_id)
