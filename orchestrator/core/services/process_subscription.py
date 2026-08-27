# Copyright 2026 GÉANT.
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

from orchestrator.core.db import ProcessSubscriptionTable, db
from pydantic_forms.types import UUIDstr


def store_process_subscription_relation(process_id: UUID | UUIDstr, subscription_id: UUID | UUIDstr) -> None:
    """Idempotently create a Process Subscription relation.

    This method can get simplified once the `store_process_subscription` step has been removed from the codebase.
    """

    process_subscription_exists = db.session.query(
        db.session.query(ProcessSubscriptionTable)
        .where(
            ProcessSubscriptionTable.process_id == process_id,
            ProcessSubscriptionTable.subscription_id == subscription_id,
        )
        .exists()
    ).scalar()

    if not process_subscription_exists:
        process_subscription = ProcessSubscriptionTable(process_id=process_id, subscription_id=subscription_id)
        db.session.add(process_subscription)
