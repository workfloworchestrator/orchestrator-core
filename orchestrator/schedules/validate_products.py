# Copyright 2019-2020 SURF.
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
from sqlalchemy import func, select

from orchestrator.db import db
from orchestrator.db.models import ProcessTable
from orchestrator.schedules.scheduling import scheduler
from orchestrator.services.processes import start_process


@scheduler(name="Validate Products and inactive subscriptions", time_unit="day", at="02:30")
def validate_products() -> None:
    uncompleted_products = db.session.scalar(
        select(func.count())
        .select_from(ProcessTable)
        .filter(ProcessTable.workflow.name == "validate_products", ProcessTable.last_status != "completed")
    )
    if not uncompleted_products:
        start_process("task_validate_products")
