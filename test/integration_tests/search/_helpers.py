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

"""Shared builder for seeding rows in the search index from integration tests."""

from uuid import UUID

from sqlalchemy_utils import Ltree

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.indexing.indexer import Indexer


def index_row(
    entity_id: UUID | str,
    path: str,
    value: str,
    title: str = "title",
    embedding: list[float] | None = None,
    *,
    entity_type: EntityType = EntityType.SUBSCRIPTION,
    value_type: FieldType = FieldType.STRING,
) -> AiSearchIndex:
    """Build an `AiSearchIndex` row with the content hash the indexer would compute, so it reads as real data."""
    return AiSearchIndex(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_title=title,
        path=Ltree(path),
        value=value,
        value_type=value_type,
        content_hash=Indexer._compute_content_hash(path, value, value_type, title),
        embedding=embedding,
    )
