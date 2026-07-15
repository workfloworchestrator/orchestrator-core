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

"""Integration tests for the trigger-maintained ai_search_paths distinct-paths table."""

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import FieldType
from orchestrator.core.search.indexing import rebuild_search_paths


def _add_index_row(
    path: str,
    *,
    value_type: FieldType = FieldType.STRING,
    entity_type: str = "SUBSCRIPTION",
    entity_id: UUID | None = None,
    value: str = "v",
) -> UUID:
    """Insert one ai_search_index row (fires the maintain trigger) and return its entity_id."""
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


def _refcount(path: str, value_type: FieldType, entity_type: str = "SUBSCRIPTION") -> int | None:
    """Return the refcount for a tuple in ai_search_paths, or None if the row is absent."""
    row = db.session.execute(
        text(
            "SELECT refcount FROM ai_search_paths "
            "WHERE entity_type = :et AND path::text = :p AND value_type = CAST(:vt AS field_type)"
        ),
        {"et": entity_type, "p": path, "vt": value_type.value},
    ).fetchone()
    return row[0] if row else None


def test_insert_creates_path_with_refcount_one():
    _add_index_row("subscription.node.name")
    assert _refcount("subscription.node.name", FieldType.STRING) == 1


def test_second_entity_same_tuple_increments_refcount():
    _add_index_row("subscription.node.name")
    _add_index_row("subscription.node.name")
    assert _refcount("subscription.node.name", FieldType.STRING) == 2


def test_delete_one_of_two_keeps_row_at_one():
    first = _add_index_row("subscription.node.name")
    _add_index_row("subscription.node.name")
    db.session.query(AiSearchIndex).filter(AiSearchIndex.entity_id == first).delete(synchronize_session=False)
    db.session.flush()
    assert _refcount("subscription.node.name", FieldType.STRING) == 1


def test_delete_last_removes_row():
    eid = _add_index_row("subscription.node.name")
    db.session.query(AiSearchIndex).filter(AiSearchIndex.entity_id == eid).delete(synchronize_session=False)
    db.session.flush()
    assert _refcount("subscription.node.name", FieldType.STRING) is None


def test_update_value_type_moves_refcount_between_tuples():
    eid = _add_index_row("subscription.node.enabled", value_type=FieldType.STRING)
    db.session.query(AiSearchIndex).filter(AiSearchIndex.entity_id == eid).update(
        {"value_type": FieldType.BOOLEAN}, synchronize_session=False
    )
    db.session.flush()
    assert _refcount("subscription.node.enabled", FieldType.STRING) is None
    assert _refcount("subscription.node.enabled", FieldType.BOOLEAN) == 1


def test_reindex_same_tuple_is_noop():
    eid = _add_index_row("subscription.node.name", value="old")
    db.session.query(AiSearchIndex).filter(AiSearchIndex.entity_id == eid).update(
        {"value": "new"}, synchronize_session=False
    )
    db.session.flush()
    assert _refcount("subscription.node.name", FieldType.STRING) == 1


def test_distinct_tuples_tracked_separately():
    _add_index_row("subscription.node.name", entity_type="SUBSCRIPTION")
    _add_index_row("subscription.node.name", entity_type="PRODUCT")
    assert _refcount("subscription.node.name", FieldType.STRING, "SUBSCRIPTION") == 1
    assert _refcount("subscription.node.name", FieldType.STRING, "PRODUCT") == 1


def _all_paths_rows() -> set[tuple]:
    """Return the full ai_search_paths contents as a comparable set."""
    rows = db.session.execute(
        text("SELECT entity_type, path::text, value_type::text, refcount FROM ai_search_paths")
    ).fetchall()
    return {tuple(r) for r in rows}


def _expected_paths_rows() -> set[tuple]:
    """Recompute the expected distinct-paths contents directly from ai_search_index."""
    rows = db.session.execute(
        text(
            "SELECT entity_type, path::text, value_type::text, count(*) "
            "FROM ai_search_index GROUP BY entity_type, path, value_type"
        )
    ).fetchall()
    return {tuple(r) for r in rows}


def test_rebuild_reconstructs_exact_table_after_drift():
    _add_index_row("subscription.node.name")
    _add_index_row("subscription.node.name")
    _add_index_row("subscription.node.speed", value_type=FieldType.INTEGER)

    # Corrupt the derived table: wrong refcount, a spurious row, and a missing row.
    db.session.execute(text("UPDATE ai_search_paths SET refcount = 99 WHERE path::text = 'subscription.node.name'"))
    db.session.execute(
        text(
            "INSERT INTO ai_search_paths (entity_type, path, value_type, refcount) "
            "VALUES ('SUBSCRIPTION', 'bogus.path'::ltree, CAST('string' AS field_type), 5)"
        )
    )
    db.session.execute(text("DELETE FROM ai_search_paths WHERE path::text = 'subscription.node.speed'"))
    db.session.flush()

    rebuild_search_paths()

    assert _all_paths_rows() == _expected_paths_rows()


def test_rebuild_on_empty_index_yields_empty_table():
    _add_index_row("subscription.node.name")
    db.session.query(AiSearchIndex).delete(synchronize_session=False)
    db.session.flush()
    rebuild_search_paths()
    assert _all_paths_rows() == set()
