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

"""Builders for seeding the search index and filtering it in retrieval integration tests."""

from uuid import UUID, uuid4

from sqlalchemy_utils import Ltree

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import BooleanOperator, EntityType, FieldType, FilterOp, UIType
from orchestrator.core.search.filters import EqualityFilter, FilterTree, PathFilter
from orchestrator.core.settings import llm_settings


def vec(axis: int) -> list[float]:
    """A unit vector on one axis, so distances between seeded embeddings are controllable."""
    vector = [0.0] * llm_settings.EMBEDDING_DIMENSION
    vector[axis] = 1.0
    return vector


def index_row(
    entity_id: UUID, path: str, value: str, title: str, embedding: list[float] | None = None
) -> AiSearchIndex:
    return AiSearchIndex(
        entity_type=EntityType.SUBSCRIPTION,
        entity_id=entity_id,
        entity_title=title,
        path=Ltree(path),
        value=value,
        value_type=FieldType.STRING,
        content_hash=uuid4().hex,
        embedding=embedding,
    )


def eq_leaf(path: str, value: str) -> PathFilter:
    return PathFilter(path=path, condition=EqualityFilter(op=FilterOp.EQ, value=value), value_kind=UIType.STRING)


def and_tree(*leaves: PathFilter) -> FilterTree:
    return FilterTree(op=BooleanOperator.AND, children=list(leaves))
