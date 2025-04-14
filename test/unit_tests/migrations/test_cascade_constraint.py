# Copyright 2019-2025 GÉANT, SURF, ESnet
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

from orchestrator.db import db
from orchestrator.db.models import InputStateTable, ProcessTable


@pytest.fixture
def create_input_state():
    """Fixture to create an input state."""

    def _create_input_state(process_id, input_state, input_type, **kwargs):
        input_state_entry = InputStateTable(
            process_id=process_id, input_state=input_state, input_type=input_type, **kwargs
        )
        db.session.add(input_state_entry)
        db.session.commit()
        return input_state_entry

    return _create_input_state


def test_cascade_delete(mocked_processes, test_client, create_input_state):
    # Create a process and related input state
    processes = test_client.get("/api/processes").json()
    # Create an input state for the first process
    create_input_state(
        process_id=processes[0]["process_id"],
        input_state={"key": "value"},
        input_type="initial_state",
    )

    # Verify both records exist
    assert db.session.query(ProcessTable).count() == 9
    assert db.session.query(InputStateTable).count() == 1

    # Delete one of the process so that the input state is deleted as well
    process = db.session.query(ProcessTable).filter_by(process_id=processes[0]["process_id"]).one()
    db.session.delete(process)
    db.session.commit()

    # Verify cascade delete
    assert db.session.query(ProcessTable).count() == 8
    assert db.session.query(InputStateTable).count() == 0
