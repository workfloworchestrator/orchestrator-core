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

"""How the fuzzy retriever restricts trigram hits to the candidate entities."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import Select, select
from sqlalchemy.orm import aliased
from sqlalchemy_utils import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import EntityType, FieldType, FilterOp, UIType
from orchestrator.core.search.filters import EqualityFilter, FilterTree, PathFilter
from orchestrator.core.search.query.builder import build_candidate_query
from orchestrator.core.search.query.queries import SelectQuery
from orchestrator.core.search.retrieval.retrievers.fuzzy import FuzzyRetriever

TERM = "Coffee grinder CG-2000-XL"


def _index_row(entity_id: UUID, path: str, value: str, title: str) -> AiSearchIndex:
    return AiSearchIndex(
        entity_type=EntityType.SUBSCRIPTION,
        entity_id=entity_id,
        entity_title=title,
        path=Ltree(path),
        value=value,
        value_type=FieldType.STRING,
        content_hash=uuid4().hex,
    )


@pytest.fixture
def seeded() -> dict[str, UUID]:
    """An active match, a terminated match, and an active subscription the term does not match."""
    ids = {"active_match": uuid4(), "terminated_match": uuid4(), "active_other": uuid4()}
    rows = [
        _index_row(ids["active_match"], "subscription.description", TERM, "active match"),
        _index_row(ids["active_match"], "subscription.status", "active", "active match"),
        _index_row(ids["terminated_match"], "subscription.description", "Coffee grinder CG-2000-XS", "terminated"),
        _index_row(ids["terminated_match"], "subscription.status", "terminated", "terminated"),
        _index_row(ids["active_other"], "subscription.description", "Espresso machine EM-500", "other"),
        _index_row(ids["active_other"], "subscription.status", "active", "other"),
    ]
    db.session.add_all(rows)
    db.session.commit()
    return ids


def _production_candidates() -> Select:
    """The shape `build_candidate_query` produces: an entity type predicate plus filters as EXISTS."""
    status_active = PathFilter(
        path="subscription.status", condition=EqualityFilter(op=FilterOp.EQ, value="active"), value_kind=UIType.STRING
    )
    query = SelectQuery(
        entity_type=EntityType.SUBSCRIPTION, query_text=TERM, filters=FilterTree.from_flat_and([status_active])
    )
    return build_candidate_query(query)


def _joined_candidates() -> Select:
    """A shape the guard rejects, so the candidate subquery has to be joined."""
    status_row = aliased(AiSearchIndex)
    return (
        select(AiSearchIndex.entity_id, AiSearchIndex.entity_title)
        .join(status_row, status_row.entity_id == AiSearchIndex.entity_id)
        .where(status_row.value == "active")
        .distinct()
    )


RESTRICTION_SQL = {"probe": "candidate_members", "join": "JOIN (SELECT DISTINCT"}


@pytest.mark.parametrize(
    "candidate_query,restriction",
    [
        pytest.param(_production_candidates, "probe", id="production_shape_probes_membership_per_hit"),
        pytest.param(_joined_candidates, "join", id="other_shapes_join_the_candidate_subquery"),
    ],
)
def test_trigram_hits_are_restricted_to_the_candidates(seeded, candidate_query, restriction):
    """Both restrictions return the same rows; only the production shape keeps the trigram index driving."""
    stmt = FuzzyRetriever(TERM, cursor=None).apply(candidate_query())

    rows = db.session.execute(stmt).mappings().all()

    assert {name for name, fragment in RESTRICTION_SQL.items() if fragment in str(stmt)} == {restriction}
    assert [(row.entity_id, float(row.score), row.highlight_path) for row in rows] == [
        (seeded["active_match"], 1.0, "subscription.description")
    ]
