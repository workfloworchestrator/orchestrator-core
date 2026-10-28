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

"""A seeded synthetic corpus of entities, built by a `Profile`.

The same profile, seed and size give the same corpus, so nothing large has to be committed. A corpus holds the
profile's *anchors*, a small fixed set of hand-designed entities that hand-written queries refer to by key, and
generated entities that fill the index to a realistic size.

Entities are Pydantic models, indexed through the real `BaseTraverser`, so paths and field types are those of
production subscriptions: nested blocks, lists and many fields at different depths.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from orchestrator.core.db import SubscriptionTable
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.indexing.registry import EntityConfig
from orchestrator.core.search.indexing.traverse import BaseTraverser

# What a profile's entity facts are called, so that query generation can perturb them without knowing the profile.
DESCRIPTION = "description"  # the entity's full title text
IDENTIFIER = "identifier"  # a short token naming a resource: a node, a prefix, ...
CUSTOMER = "customer"
LOCATION = "location"


@dataclass(frozen=True)
class CorpusEntity:
    """An entity to index, with the facts queries are generated from.

    Attributes:
        key: Stable handle. Anchors are referred to by it from hand-written queries.
        entity_id: The id the entity is indexed under, and the id search results are scored by.
        model: What gets indexed, traversed like a subscription model.
        facts: Texts the entity can be searched by, keyed by `DESCRIPTION`, `IDENTIFIER`, `CUSTOMER` and `LOCATION`.
            A fact can have several values (a service with two ends has two identifiers and two locations): queries
            are made from the first, and a query for any of them counts the entity as a right answer.
    """

    key: str
    entity_id: UUID
    model: BaseModel
    facts: Mapping[str, tuple[str, ...]]


class Profile(Protocol):
    """Templates, naming patterns and block structure of a corpus. Downstream users supply their own."""

    name: str

    def anchors(self) -> Sequence[CorpusEntity]:
        """The fixed entities hand-written queries refer to. Must not depend on the seed."""
        ...

    def generate(self, rng: Random, count: int) -> Sequence[CorpusEntity]:
        """`count` entities drawn with `rng`, none of which clash with the anchors' identifiers."""
        ...


@dataclass(frozen=True)
class Corpus:
    """The entities of one profile, seed and size."""

    profile: str
    seed: int
    entities: tuple[CorpusEntity, ...]

    @property
    def by_key(self) -> dict[str, CorpusEntity]:
        return {entity.key: entity for entity in self.entities}


def build_corpus(profile: Profile, seed: int, size: int) -> Corpus:
    """The anchors of `profile` plus `size` generated entities.

    Raises:
        ValueError: When two entities share a key or an id.
    """
    entities = (*profile.anchors(), *profile.generate(Random(seed), size))  # noqa: S311 - reproducible, not secret
    for attribute in ("key", "entity_id"):
        values = [getattr(entity, attribute) for entity in entities]
        if len(set(values)) != len(values):
            raise ValueError(f"Profile {profile.name!r} produced duplicate entity {attribute}s")
    return Corpus(profile=profile.name, seed=seed, entities=entities)


class CorpusTraverser(BaseTraverser):
    """Traverses a `CorpusEntity`'s model with the same field handling as a subscription."""

    @classmethod
    def _load_model(cls, entity: CorpusEntity) -> BaseModel:
        return entity.model


CORPUS_ENTITY_CONFIG = EntityConfig(
    entity_kind=EntityType.SUBSCRIPTION,
    table=SubscriptionTable,
    traverser=CorpusTraverser,
    pk_name="entity_id",
    root_name="subscription",
    title_paths=["subscription.description"],
)
