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

"""Tests that the fork-column check constraint migrates up and down.

These run against the throwaway database of the ``throwaway_migrate_uri`` fixture instead of the test database,
because they rewrite its schema. What the constraint does to a row is covered by ``test_parallel_db.py`` against the
migrated test database; here it is only the migration itself.
"""

from collections.abc import Iterator
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from orchestrator.core.testing.fixtures import make_alembic_config

pytestmark = pytest.mark.postgres

# Pinned, so a later migration does not change what these tests exercise.
REVISION = "06300482cd05"
PREVIOUS_REVISION = "18a7c2676fd3"
CONSTRAINT_NAME = "ck_process_steps_branch_kind_count_set_together"


def _current_revision(engine: Engine) -> str:
    with engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def _fork_check_constraint(engine: Engine) -> tuple[str, bool] | None:
    """The definition and `convalidated` flag of the constraint, or None when it is absent."""
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT pg_get_constraintdef(oid), convalidated FROM pg_constraint "
                "WHERE conrelid = 'process_steps'::regclass AND contype = 'c' AND conname = :conname"
            ),
            {"conname": CONSTRAINT_NAME},
        ).one_or_none()


@pytest.fixture()
def engine(throwaway_migrate_uri: str) -> Iterator[Engine]:
    """An engine on the throwaway database, unrelated to the test database."""
    test_engine = create_engine(throwaway_migrate_uri)
    yield test_engine
    test_engine.dispose()


@pytest.fixture()
def config(throwaway_migrate_uri: str) -> Config:
    """The migration chain, pointed at the throwaway database."""
    return make_alembic_config(throwaway_migrate_uri)


@pytest.fixture()
def migrated_engine(engine: Engine, config: Config) -> Engine:
    """The throwaway database, migrated to the revision under test."""
    command.upgrade(config, REVISION)
    return engine


@pytest.fixture()
def process_id(migrated_engine: Engine) -> UUID:
    """A process to hang process steps on, with its own workflow row."""
    with migrated_engine.connect() as conn:
        workflow_id = conn.execute(
            text(
                "INSERT INTO workflows (name, description, target, is_task) "
                "VALUES ('migration test workflow', '', 'SYSTEM', false) RETURNING workflow_id"
            )
        ).scalar_one()
        process_id = conn.execute(
            text(
                "INSERT INTO processes (workflow_id, last_status, created_by, assignee, is_task) "
                "VALUES (:workflow_id, 'created', 'migration test', 'SYSTEM', false) RETURNING pid"
            ),
            {"workflow_id": workflow_id},
        ).scalar_one()
        conn.commit()
    return process_id


def _insert_step(engine: Engine, process_id: UUID, branch_kind: str | None, branch_count: int | None) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO process_steps (pid, name, status, state, branch_kind, branch_count) "
                "VALUES (:pid, 'migration test step', 'success', '{}'::jsonb, :kind, :count)"
            ),
            {"pid": process_id, "kind": branch_kind, "count": branch_count},
        )


def test_upgrade_adds_a_validated_check_constraint(migrated_engine: Engine) -> None:
    assert _current_revision(migrated_engine) == REVISION
    assert _fork_check_constraint(migrated_engine) == (
        "CHECK (((branch_kind IS NULL) = (branch_count IS NULL)))",
        True,
    )


def test_downgrade_drops_the_constraint_and_upgrade_puts_it_back(
    process_id: UUID, engine: Engine, config: Config
) -> None:
    command.downgrade(config, PREVIOUS_REVISION)
    assert _current_revision(engine) == PREVIOUS_REVISION
    assert _fork_check_constraint(engine) is None

    # Without the constraint, a half-set row is accepted.
    _insert_step(engine, process_id, "parallel", None)

    # Remove the half-set row before reapplying the validating constraint.
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM process_steps WHERE pid = :pid"), {"pid": process_id})
        conn.commit()

    command.upgrade(config, REVISION)
    assert _current_revision(engine) == REVISION
    assert _fork_check_constraint(engine) is not None
    with pytest.raises(IntegrityError, match=CONSTRAINT_NAME):
        _insert_step(engine, process_id, "parallel", None)
