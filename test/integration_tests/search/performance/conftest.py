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

import pytest
from sqlalchemy import text

from orchestrator.core.db import db

SORTSUPPORT = "FUNCTION 11 (ltree, ltree)"


def _alter_gist_ltree_ops(action):
    with db.wrapped_database.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f"ALTER OPERATOR FAMILY gist_ltree_ops USING gist {action}"))
    db.wrapped_database.engine.dispose()


@pytest.fixture(scope="package", autouse=True)
def sorted_gist_build(database):
    """Have REINDEX build the GiST path index sorted, so it is the same on every build.

    Built by insertion, GiST breaks ties between equally good subtrees with a per-backend random number, so the same
    rows give a different index size per build, and that size changes the planner's choice to use it. ltree has no
    sortsupport; byte order is no meaningful ltree order, but a sorted build is correct in any order, only less
    compact. Committed, as a test's own backend would not see the change, and dropped again so other packages test the
    index production builds.
    """
    _alter_gist_ltree_ops(f"ADD {SORTSUPPORT} bytea_sortsupport(internal)")
    yield
    _alter_gist_ltree_ops(f"DROP {SORTSUPPORT}")


@pytest.fixture
def db_session(db_session):
    """The integration tests' `db_session`, closing its connection after the test instead of returning it to the pool.

    Postgres runs each connection in its own server process, the backend, which caches catalog rows such as a Sort
    node's operators and reads their blocks only the first time. A new session on a pooled connection keeps that cache,
    so whether an earlier test already loaded them, and with it the blocks measured, would depend on test order.
    """
    yield db_session
    db.wrapped_database.engine.dispose()
