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
from orchestrator.db.models import SubscriptionInstanceAsJsonFunction


def get_subscription_instance_dict(subscription_instance_id: UUID) -> dict:
    """Query the subscription instance as aggregated JSONB and returns it as a dict.

    Note: all values are returned as lists and have to be transformed by the caller.
    It was attempted to do this in the DB query but this gave worse performance.
    """
    return db.session.execute(select(SubscriptionInstanceAsJsonFunction(subscription_instance_id))).scalar_one()
