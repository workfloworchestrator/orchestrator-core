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

"""Integration tests for list-valued response_columns against the real ai_search_index table."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.query.builder import build_response_list_rows_query, process_response_list_columns

pytestmark = pytest.mark.search


def _add_index_row(
    path: str,
    *,
    value_type: FieldType = FieldType.STRING,
    entity_type: str = "PROCESS",
    entity_id: UUID | None = None,
    value: str = "v",
) -> UUID:
    """Insert one ai_search_index row and return its entity_id."""
    eid = entity_id or uuid4()
    db.session.add(
        AiSearchIndex(
            entity_type=entity_type,
            entity_id=eid,
            path=Ltree(path),
            value=value,
            content_hash="0" * 64,
            value_type=value_type,
        )
    )
    db.session.flush()
    return eid


def test_list_rows_query_returns_grouped_subscriptions_in_order():
    process_id = uuid4()
    _add_index_row("process.subscriptions.0.subscription_id", entity_id=process_id, value="uuid1")
    _add_index_row("process.subscriptions.0.description", entity_id=process_id, value="desc1")
    _add_index_row("process.subscriptions.1.subscription_id", entity_id=process_id, value="uuid2")
    _add_index_row("process.subscriptions.1.description", entity_id=process_id, value="desc2")

    list_paths = ["process.subscriptions.*.subscription_id", "process.subscriptions.*.description"]
    stmt = build_response_list_rows_query([str(process_id)], EntityType.PROCESS, list_paths)
    rows = db.session.execute(stmt).all()

    result = process_response_list_columns(rows, list_paths)

    assert result == {
        "process.subscriptions": {
            str(process_id): [
                {"subscription_id": "uuid1", "description": "desc1"},
                {"subscription_id": "uuid2", "description": "desc2"},
            ]
        }
    }


def test_list_rows_query_excludes_other_entities_and_entity_types():
    process_id = uuid4()
    other_process_id = uuid4()
    _add_index_row("process.subscriptions.0.subscription_id", entity_id=process_id, value="uuid1")
    _add_index_row("process.subscriptions.0.subscription_id", entity_id=other_process_id, value="uuid-other")
    # Same path shape but a different entity_type -- must not leak in.
    _add_index_row(
        "process.subscriptions.0.subscription_id", entity_id=uuid4(), entity_type="SUBSCRIPTION", value="uuid-sub"
    )

    list_paths = ["process.subscriptions.*.subscription_id"]
    stmt = build_response_list_rows_query([str(process_id)], EntityType.PROCESS, list_paths)
    rows = db.session.execute(stmt).all()

    result = process_response_list_columns(rows, list_paths)

    assert result == {"process.subscriptions": {str(process_id): [{"subscription_id": "uuid1"}]}}


def test_list_rows_query_returns_empty_when_no_subscriptions_indexed():
    process_id = uuid4()
    _add_index_row("process.workflow_name", entity_id=process_id, value="create_service")

    list_paths = ["process.subscriptions.*.subscription_id"]
    stmt = build_response_list_rows_query([str(process_id)], EntityType.PROCESS, list_paths)
    rows = db.session.execute(stmt).all()

    result = process_response_list_columns(rows, list_paths)

    assert result == {"process.subscriptions": {}}


def test_list_rows_query_multiple_prefixes_in_one_round_trip():
    """Wildcard paths with two distinct prefixes are fetched together and split back out by prefix."""
    process_id = uuid4()
    _add_index_row("process.subscriptions.0.subscription_id", entity_id=process_id, value="uuid1")
    _add_index_row("process.products.0.name", entity_id=process_id, value="product1")

    list_paths = ["process.subscriptions.*.subscription_id", "process.products.*.name"]
    stmt = build_response_list_rows_query([str(process_id)], EntityType.PROCESS, list_paths)
    rows = db.session.execute(stmt).all()

    result = process_response_list_columns(rows, list_paths)

    assert result == {
        "process.subscriptions": {str(process_id): [{"subscription_id": "uuid1"}]},
        "process.products": {str(process_id): [{"name": "product1"}]},
    }
