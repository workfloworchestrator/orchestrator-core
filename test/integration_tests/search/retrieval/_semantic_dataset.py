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

"""Deterministic synthetic corpus for the semantic retrieval tests.

Nothing here is real data. Vectors are bag-of-token sums, so texts that share tokens are close.
"""

import math
from random import Random
from typing import NamedTuple
from uuid import UUID, uuid5

from sqlalchemy.orm import Session

from orchestrator.core.search.core.types import EntityType
from orchestrator.core.settings import llm_settings
from test.integration_tests.search._embeddings import add_indexed_row

NAMESPACE = UUID("6f1c2a52-0f3e-4c53-9a54-0d3a4f0a7e11")
ENTITY_COUNT = 40
# The axes of a token are drawn with randrange(dimension), so the vectors, and with them semantic_scores.json, are
# only valid for the dimension they were recorded with.
SNAPSHOT_DIMENSION = 1536
AXES_PER_TOKEN = 6
BOUNDED_CANDIDATES_LIMIT = 1000

STATUSES = ("active", "provisioning", "terminated")
PRODUCTS = ("Fiber access", "Light path", "Layer 2 VPN", "IP peering")
CUSTOMERS = ("Acme", "Globex", "Initech")
ADJECTIVES = ("redundant", "primary", "backup", "metro", "campus", "research")
NOUNS = ("circuit", "uplink", "tunnel", "peering", "service", "link")

# Representative queries, from near-duplicate of a seeded text to loosely related wording.
QUERIES = (
    "redundant metro circuit",
    "active",
    "Fiber access",
    "backup uplink for campus",
    "peering with Globex",
    "terminated research tunnel",
)


class CorpusRow(NamedTuple):
    entity_id: UUID
    title: str
    path: str
    value: str
    embedded: bool


def _token_vector(token: str) -> list[tuple[int, float]]:
    rng = Random(f"axes:{token}")  # noqa: S311 - seeded on purpose, the corpus must be reproducible
    return [(rng.randrange(llm_settings.EMBEDDING_DIMENSION), rng.choice((-1.0, 1.0))) for _ in range(AXES_PER_TOKEN)]


def embed(text: str) -> list[float]:
    """Unit vector for a text, deterministic and stable across runs and platforms."""
    vector = [0.0] * llm_settings.EMBEDDING_DIMENSION
    for axis, sign in (pair for token in text.lower().split() for pair in _token_vector(token)):
        vector[axis] += sign
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [round(v / norm, 6) for v in vector]


def entity_id(index: int) -> UUID:
    return uuid5(NAMESPACE, f"subscription-{index}")


def _rows_for(index: int) -> list[CorpusRow]:
    eid = entity_id(index)
    title = f"subscription {index}"
    description = f"{ADJECTIVES[index % len(ADJECTIVES)]} {PRODUCTS[index % len(PRODUCTS)].lower()} {NOUNS[index % len(NOUNS)]} {index}"
    fields = (
        ("subscription.description", description, True),
        ("subscription.status", STATUSES[index % len(STATUSES)], True),
        ("subscription.product.name", PRODUCTS[index % len(PRODUCTS)], True),
        ("subscription.customer.name", CUSTOMERS[index % len(CUSTOMERS)], True),
        ("subscription.insync", str(index % 2 == 0).lower(), False),
    )
    return [CorpusRow(eid, title, path, value, embedded) for path, value, embedded in fields]


def corpus() -> list[CorpusRow]:
    """All rows of the corpus. Low-cardinality fields repeat across entities on purpose."""
    return [row for index in range(ENTITY_COUNT) for row in _rows_for(index)]


def vector_for(row: CorpusRow) -> list[float] | None:
    """The vector of a row, or None when it is not embedded. The embedded text is ``"{path}: {value}"``."""
    return embed(f"{row.path}: {row.value}") if row.embedded else None


def seed_corpus(session: Session) -> None:
    """Add the whole corpus to the session through ``add_indexed_row``. The caller commits."""
    for row in corpus():  # a side effect per row, not a collection that is built
        add_indexed_row(
            session,
            entity_type=EntityType.SUBSCRIPTION,
            entity_id=row.entity_id,
            path=row.path,
            value=row.value,
            embedding=vector_for(row),
            title=row.title,
        )
