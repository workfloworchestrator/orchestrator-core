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
import contextlib
from contextvars import ContextVar
from typing import Iterator
from uuid import UUID

from orchestrator.domain import SubscriptionModel
from pydantic_forms.types import UUIDstr

__subscription_model_cache: ContextVar[dict[UUID, SubscriptionModel] | None] = ContextVar(
    "subscription_model_cache", default=None
)


@contextlib.contextmanager
def cache_subscription_models() -> Iterator:
    """Caches SubscriptionModels for the duration of the context.

    Inside this context, calling SubscriptionModel.from_subscription() twice with the same
    subscription id will return the same instance.

    The primary usecase is to improve performance of `@computed_field` properties on product blocks
    which load other subscriptions.

    Example usage:
        subscription = SubscriptionModel.from_subscription("...")
        with cache_subscription_models():
           subscription_dict = subscription.model_dump()
    """
    if __subscription_model_cache.get() is not None:
        # If it's already active in the current context, we do nothing.
        # This makes the contextmanager reentrant.
        # The outermost contextmanager will eventually reset the context.
        yield
        return

    before = __subscription_model_cache.set({})
    try:
        yield
    finally:
        __subscription_model_cache.reset(before)


def get_from_cache(subscription_id: UUID | UUIDstr) -> SubscriptionModel | None:
    """Retrieve SubscriptionModel from cache, if present."""
    if (cache := __subscription_model_cache.get()) is None:
        return None

    id_ = subscription_id if isinstance(subscription_id, UUID) else UUID(subscription_id)
    return cache.get(id_, None)


def store_in_cache(model: SubscriptionModel) -> None:
    """Store SubscriptionModel in cache, if required."""
    if (cache := __subscription_model_cache.get()) is None:
        return

    cache[model.subscription_id] = model
