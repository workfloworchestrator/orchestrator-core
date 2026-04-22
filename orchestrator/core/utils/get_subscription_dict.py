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

from uuid import UUID

from orchestrator.core.domain.base import SubscriptionModel
from orchestrator.core.services.subscriptions import _generate_etag, build_domain_model, build_extended_domain_model


async def get_subscription_dict(subscription_id: UUID, inject_inuseby: bool = True) -> tuple[dict, str]:
    """Helper function to get subscription dict by uuid from db or cache."""

    subscription_model = SubscriptionModel.from_subscription(subscription_id)

    if not inject_inuseby:
        subscription = build_domain_model(subscription_model)
    else:
        subscription = build_extended_domain_model(subscription_model)
    etag = _generate_etag(subscription)
    return subscription, etag
