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
from uuid import UUID

from sqlalchemy import select

from orchestrator.db import db
from orchestrator.db.models import UserInputTable


def _retrieve_user_input(process_id: UUID, step_name: str | None = None) -> UserInputTable:
    """Get user input.

    Args:
        process_id: Process ID
        step_name: Step name

    Returns:
        User input table

    """
    if step_name:
        return db.session.execute(
            select(UserInputTable)
            .filter(UserInputTable.process_id == process_id)
            .filter(UserInputTable.step_name == step_name)
        ).scalar_one()
    return db.session.execute(select(UserInputTable).filter(UserInputTable.process_id == process_id)).scalar_one()


def _store_user_input(process_id: UUID, user_input: list[dict], step_name: str | None = None) -> None:
    db.session.add(
        UserInputTable(
            process_id=process_id,
            user_input=user_input,
            step_name=step_name,
        )
    )
    db.session.commit()
