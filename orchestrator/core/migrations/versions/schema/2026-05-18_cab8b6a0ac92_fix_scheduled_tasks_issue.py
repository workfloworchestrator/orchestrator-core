# Copyright 2019-2026 SURF, ESnet, GÉANT.
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
"""Fix issue where scheduled tasks are not shown due to namespace change from orchestrator. to orchestrator.core.

Revision ID: cab8b6a0ac92
Revises: be3163f7c49d
Create Date: 2026-05-18 11:49:37.145417

"""
import pickle

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'cab8b6a0ac92'
down_revision = 'be3163f7c49d'
branch_labels = None
depends_on = None

OLD_PREFIX = "orchestrator."
NEW_PREFIX = "orchestrator.core."

def _rewrite_func_ref(func_ref: str, old: str, new: str) -> str | None:
    """Rewrite a func ref from old prefix to new, returning None if unchanged."""
    if func_ref.startswith(old) and not func_ref.startswith(new):
        return new + func_ref[len(old) :]
    return None


def _migrate_job_states(old: str, new: str) -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, job_state FROM apscheduler_jobs")).fetchall()

    for job_id, job_state in rows:
        state = pickle.loads(job_state)  # noqa: S301
        updated_ref = _rewrite_func_ref(state.get("func", ""), old, new)
        if updated_ref:
            state["func"] = updated_ref
            conn.execute(
                sa.text("UPDATE apscheduler_jobs SET job_state = :state WHERE id = :id"),
                {"state": pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL), "id": job_id},
            )


def upgrade() -> None:
    _migrate_job_states(OLD_PREFIX, NEW_PREFIX)


def downgrade() -> None:
    _migrate_job_states(NEW_PREFIX, OLD_PREFIX)
