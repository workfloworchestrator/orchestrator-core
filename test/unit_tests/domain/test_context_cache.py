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

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from orchestrator.core.domain.context_cache import (
    cache_subscription_models,
    evict_from_cache,
    get_from_cache,
    no_subscription_model_cache,
    store_in_cache,
)


def test_no_subscription_model_cache_disables_cache_inside_active_scope() -> None:
    """Inside an active cache_subscription_models() scope, the bypass forces fresh reads."""
    model = MagicMock()
    model.subscription_id = uuid4()

    with cache_subscription_models():
        store_in_cache(model)
        assert get_from_cache(model.subscription_id) is model

        with no_subscription_model_cache():
            assert get_from_cache(model.subscription_id) is None
            store_in_cache(MagicMock(subscription_id=model.subscription_id))

        assert get_from_cache(model.subscription_id) is model  # outer cache survives the bypass untouched


def test_evict_from_cache_removes_planned_ids() -> None:
    """Evicting planned ids leaves the rest of the cache intact."""
    model = MagicMock()
    model.subscription_id = uuid4()
    other = MagicMock()
    other.subscription_id = uuid4()

    with cache_subscription_models():
        store_in_cache(model)
        store_in_cache(other)

        evict_from_cache([str(model.subscription_id)])  # string ids are accepted like get_from_cache's

        assert get_from_cache(model.subscription_id) is None
        assert get_from_cache(other.subscription_id) is other


def test_evict_from_cache_is_inert_without_an_active_cache() -> None:
    """No cache scope at all, or an active bypass scope: eviction is a no-op, not a resurrection."""
    evict_from_cache([uuid4()])

    model = MagicMock()
    model.subscription_id = uuid4()
    with cache_subscription_models(), no_subscription_model_cache():
        store_in_cache(model)  # inert inside the bypass scope
        evict_from_cache([model.subscription_id])
    assert get_from_cache(model.subscription_id) is None


def test_fresh_cache_isolates_each_attempt_and_restores_outer_models() -> None:
    """Reusing an inherited model, or leaking attempt models outward, breaks freshness."""
    subscription_id, attempt_only_id = uuid4(), uuid4()
    outer = MagicMock(subscription_id=subscription_id)
    attempt = MagicMock(subscription_id=subscription_id)
    inner = MagicMock(subscription_id=subscription_id)

    with cache_subscription_models():
        store_in_cache(outer)
        with cache_subscription_models(fresh=True):
            assert get_from_cache(subscription_id) is None
            store_in_cache(attempt)
            store_in_cache(MagicMock(subscription_id=attempt_only_id))
            with cache_subscription_models(fresh=True):
                assert get_from_cache(subscription_id) is None
                assert get_from_cache(attempt_only_id) is None
                store_in_cache(inner)
                assert get_from_cache(subscription_id) is inner
            assert get_from_cache(subscription_id) is attempt
        assert get_from_cache(subscription_id) is outer
        assert get_from_cache(attempt_only_id) is None
    assert get_from_cache(subscription_id) is None


def test_fresh_cache_restores_outer_models_after_exception() -> None:
    """An aborted plan must not replace its caller's cache with partial attempt state."""
    subscription_id = uuid4()
    outer = MagicMock(subscription_id=subscription_id)
    with cache_subscription_models():
        store_in_cache(outer)
        with pytest.raises(ValueError, match="planning failed"), cache_subscription_models(fresh=True):
            assert get_from_cache(subscription_id) is None
            store_in_cache(MagicMock(subscription_id=subscription_id))
            raise ValueError("planning failed")
        assert get_from_cache(subscription_id) is outer


def test_default_nested_cache_preserves_reentrant_reuse() -> None:
    """The new opt-in boundary must not disable reuse for ordinary nested callers."""
    model = MagicMock(subscription_id=uuid4())
    with cache_subscription_models():
        store_in_cache(model)
        with cache_subscription_models():
            assert get_from_cache(model.subscription_id) is model
            replacement = MagicMock(subscription_id=model.subscription_id)
            store_in_cache(replacement)
        assert get_from_cache(model.subscription_id) is replacement
