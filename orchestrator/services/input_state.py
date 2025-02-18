# Copyright 2019-2025 SURF.
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
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select

from orchestrator.db import db
from orchestrator.db.models import InputStateTable


def retrieve_input_state(process_id: UUID, input_type: str) -> InputStateTable:
    """Get user input.

    Args:
        process_id: Process ID
        input_type: The type of the input.

    Returns:
        User input table

    """

    res: InputStateTable | None = db.session.scalars(
        select(InputStateTable)
        .filter(InputStateTable.process_id == process_id)
        .filter(InputStateTable.input_type == input_type)
        .order_by(InputStateTable.input_time.asc())
    ).first()

    if res:
        return res
    raise ValueError(f"No input state for pid: {process_id}")


def store_input_state(
    process_id: UUID,
    input_state: dict[str, Any] | list[dict[str, Any]],
    input_type: Literal["initial_state", "user_input"],
) -> None:
    """Store user input state.

    Args:
        process_id: Process ID
        input_state: Dictionary of user input state
        input_type: The type of the input.

    Returns:
        None

    """
    db.session.add(
        InputStateTable(
            process_id=process_id,
            input_state=input_state,
            input_type=input_type,
        )
    )
    db.session.commit()
