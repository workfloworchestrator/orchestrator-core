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

"""Abbreviation queries that the fuzzy retriever has to find across a subscription's words.

A customer abbreviation and a product name in one description are separated by a word (`RUG prefix LIR`). The fuzzy
retriever matches the query as one contiguous string, so `RUG LIR` misses the description even though both words are
in it.
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy_utils import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import EntityType, FieldType, RetrieverType
from orchestrator.core.search.query.engine import execute_search
from orchestrator.core.search.query.queries import SelectQuery

TARGET = "RUG prefix LIR 192.87.22.0/24"
# Also starts with RUG and reads like a LIR service, so a match on RUG alone or LIR alone does not decide the result.
DECOYS = ["RUG LR ASD001B-GN012A ASD002A-GN001B 10 Gbit/s", "RUG L2VPN GN001B-GN012A-LW001B 1 Gbit/s"]


def _index_row(entity_id: UUID, description: str) -> AiSearchIndex:
    return AiSearchIndex(
        entity_type=EntityType.SUBSCRIPTION,
        entity_id=entity_id,
        entity_title=description,
        path=Ltree("subscription.description"),
        value=description,
        value_type=FieldType.STRING,
        content_hash=uuid4().hex,
    )


@pytest.fixture
def seeded() -> UUID:
    target = uuid4()
    rows = [_index_row(target, TARGET)] + [_index_row(uuid4(), decoy) for decoy in DECOYS]
    db.session.add_all(rows)
    db.session.commit()
    return target


@pytest.mark.parametrize(
    "query_text",
    [
        pytest.param("RUG prefix LIR", id="words_in_order"),
        pytest.param("LIR", id="single_word"),
        pytest.param(
            "RUG LIR",
            id="words_apart",
            marks=pytest.mark.xfail(
                strict=True,
                reason="The fuzzy retriever matches the query as one contiguous string. 'RUG LIR' scores below the 0.6 "
                "gate against 'RUG prefix LIR', so the description is dropped before ranking.",
            ),
        ),
    ],
)
async def test_abbreviation_query_returns_the_subscription(seeded, async_session, query_text):
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=query_text, retriever=RetrieverType.FUZZY)

    response = await execute_search(query, async_session)

    assert str(seeded) in [result.entity_id for result in response.results]
