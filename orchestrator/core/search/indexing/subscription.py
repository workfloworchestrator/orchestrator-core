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

"""Partial search-index updates for subscriptions, for changes that do not warrant a full re-index."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.indexing.indexer import Indexer
from orchestrator.core.search.indexing.registry import ENTITY_CONFIG_REGISTRY


async def update_subscription_insync_in_index(session: AsyncSession, subscription_id: str, insync: bool) -> bool:
    """Update only the indexed `subscription.insync` row, avoiding a full re-index of the subscription.

    The content hash is recomputed so a later full re-index sees no difference. The caller owns the
    transaction, so the index change commits or rolls back together with the subscription's own.

    Args:
        session: The session whose transaction the update joins. It is not committed here.
        subscription_id: The subscription whose index row to update.
        insync: The new in-sync value.

    Returns:
        True when the row was updated, False when the subscription is not indexed yet.
    """
    path = Ltree(f"{ENTITY_CONFIG_REGISTRY[EntityType.SUBSCRIPTION].root_name}.insync")
    value = str(insync)
    row_filter = (AiSearchIndex.entity_id == subscription_id, AiSearchIndex.path == path)

    stmt = select(AiSearchIndex.entity_title, AiSearchIndex.value_type).where(*row_filter)
    row = (await session.execute(stmt)).first()
    if row is None:
        return False

    content_hash = Indexer._compute_content_hash(str(path), value, row.value_type, row.entity_title)
    await session.execute(update(AiSearchIndex).where(*row_filter).values(value=value, content_hash=content_hash))
    return True
