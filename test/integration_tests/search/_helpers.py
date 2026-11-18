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

from collections.abc import Iterable
from typing import NamedTuple
from uuid import UUID

from orchestrator.core.db import db
from orchestrator.core.search.core.types import EntityType, FieldType
from test.integration_tests.search._embeddings import add_indexed_row


class SeededRow(NamedTuple):
    entity_id: UUID | str
    path: str
    value: str
    title: str
    embedding: list[float] | None
    entity_type: EntityType
    value_type: FieldType


def index_row(
    entity_id: UUID | str,
    path: str,
    value: str,
    title: str = "title",
    embedding: list[float] | None = None,
    *,
    entity_type: EntityType = EntityType.SUBSCRIPTION,
    value_type: FieldType = FieldType.STRING,
) -> SeededRow:
    """Describe an index row, with the vector of its text when it carries one. `seed_rows` writes them."""
    return SeededRow(entity_id, path, value, title, embedding, entity_type, value_type)


def seed_rows(rows: Iterable[SeededRow]) -> None:
    """Add the index rows, and the vectors of those that carry one, to the test session."""
    for row in rows:  # a side effect per row, not a collection that is built
        add_indexed_row(
            db.session,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            path=row.path,
            value=row.value,
            embedding=row.embedding,
            title=row.title,
            value_type=row.value_type,
        )
