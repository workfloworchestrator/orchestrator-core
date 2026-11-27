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
import contextlib
from collections.abc import Iterable
from contextvars import ContextVar
from typing import Iterator
from uuid import UUID

from orchestrator.core.domain import SubscriptionModel
from pydantic_forms.types import UUIDstr

__subscription_model_cache: ContextVar[dict[UUID, SubscriptionModel] | None] = ContextVar(
    "subscription_model_cache", default=None
)


@contextlib.contextmanager
def cache_subscription_models(*, fresh: bool = False) -> Iterator:
    """Caches SubscriptionModels for the duration of the context.

    Inside this context, calling SubscriptionModel.from_subscription() twice with the same
    subscription id will return the same instance.

    The primary usecase is to improve performance of `@computed_field` properties on product blocks
    which load other subscriptions.

    By default nested scopes reuse the active cache. ``fresh=True`` instead starts
    an empty cache for this scope and restores the outer cache untouched on exit.
    This isolates an index planning attempt from models loaded before its baseline.
    It does not refresh SQLAlchemy's identity map; the planner handles ORM freshness.

    Example usage:
        subscription = SubscriptionModel.from_subscription("...")
        with cache_subscription_models():
           subscription_dict = subscription.model_dump()
    """
    if not fresh and __subscription_model_cache.get() is not None:
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


@contextlib.contextmanager
def no_subscription_model_cache() -> Iterator:
    """Disables the SubscriptionModel cache for the duration of the context.

    Inside this context, SubscriptionModel.from_subscription() does not reuse a domain
    model from an enclosing cache. Its ORM loader can still reuse SQLAlchemy identity-map
    state: this helper alone does not force a SQL query or fresh database values.
    Retry planning separately refreshes ORM state and creates an attempt-local cache.

    Writes inside the context are not cached either; on exit the previously active
    cache (if any) is restored untouched.
    """
    before = __subscription_model_cache.set(None)
    try:
        yield
    finally:
        __subscription_model_cache.reset(before)


def evict_from_cache(subscription_ids: Iterable[UUID | UUIDstr]) -> None:
    """Remove the given subscriptions from the active model cache, if one is active.

    Used by index passes that just re-read a subscription's row and are about to plan
    from it: without eviction ``from_subscription()`` would return a model cached earlier
    in the run instead of the freshly read state. Inert outside a cache scope (and inside
    a ``no_subscription_model_cache()`` bypass), where there is nothing to evict.
    """
    if (cache := __subscription_model_cache.get()) is None:
        return

    for subscription_id in subscription_ids:
        id_ = subscription_id if isinstance(subscription_id, UUID) else UUID(subscription_id)
        cache.pop(id_, None)


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
