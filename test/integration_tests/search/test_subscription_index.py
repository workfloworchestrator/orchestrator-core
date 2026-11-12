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

"""Integration tests for updating only the insync row of a subscription in the search index."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import FieldType
from orchestrator.core.search.indexing.indexer import Indexer
from orchestrator.core.search.indexing.subscription import update_subscription_insync_in_index
from test.integration_tests.search._helpers import index_row

TITLE = "my subscription"


def _row(entity_id: UUID, path: str) -> AiSearchIndex:
    db.session.expire_all()
    return db.session.scalars(
        select(AiSearchIndex).where(AiSearchIndex.entity_id == entity_id, AiSearchIndex.path == Ltree(path))
    ).one()


@pytest.mark.parametrize(
    "stored, new",
    [
        pytest.param("False", True, id="false-to-true"),
        pytest.param("True", False, id="true-to-false"),
    ],
)
async def test_updates_only_the_insync_row(async_session, stored: str, new: bool) -> None:
    entity_id = uuid4()
    db.session.add(index_row(entity_id, "subscription.insync", stored, TITLE, value_type=FieldType.BOOLEAN))
    db.session.add(index_row(entity_id, "subscription.status", "active", TITLE))
    db.session.flush()

    assert await update_subscription_insync_in_index(async_session, str(entity_id), new) is True

    insync = _row(entity_id, "subscription.insync")
    assert insync.value == str(new)
    assert insync.content_hash == Indexer._compute_content_hash(
        "subscription.insync", str(new), FieldType.BOOLEAN, TITLE
    )
    assert _row(entity_id, "subscription.status").value == "active"


async def test_returns_false_when_subscription_is_not_indexed(async_session) -> None:
    assert await update_subscription_insync_in_index(async_session, str(uuid4()), True) is False
