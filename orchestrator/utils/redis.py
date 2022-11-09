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

from os import getenv
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from redis import Redis
from structlog import get_logger

from orchestrator.services.subscriptions import _generate_etag
from orchestrator.settings import app_settings
from orchestrator.utils.json import json_dumps, json_loads

logger = get_logger(__name__)

cache = Redis(host=app_settings.CACHE_HOST, port=app_settings.CACHE_PORT)

ONE_WEEK = 3600 * 24 * 7


def caching_models_enabled() -> bool:
    return getenv("AIOCACHE_DISABLE", "0") == "0" and app_settings.CACHE_DOMAIN_MODELS


def to_redis(subscription: Dict[str, Any]) -> None:
    if caching_models_enabled():
        logger.info("Setting cache for subscription.", subscription=subscription["subscription_id"])
        etag = _generate_etag(subscription)
        cache.set(f"domain:{subscription['subscription_id']}", json_dumps(subscription), ex=ONE_WEEK)
        cache.set(f"domain:etag:{subscription['subscription_id']}", etag, ex=ONE_WEEK)
    else:
        logger.warning("Caching disabled, not caching subscription", subscription=subscription["subscription_id"])


def from_redis(subscription_id: UUID) -> Optional[Tuple[Any, str]]:
    if caching_models_enabled():
        logger.info("Retrieving subscription from cache", subscription=subscription_id)
        obj = cache.get(f"domain:{subscription_id}")
        etag = cache.get(f"domain:etag:{subscription_id}")
        if obj and etag:
            return json_loads(obj), etag.decode("utf-8")
        else:
            return None
    else:
        logger.warning("Caching disabled, not loading subscription", subscription=subscription_id)
        return None


def delete_from_redis(subscription_id: UUID) -> None:
    if caching_models_enabled():
        logger.info("Deleting subscription object from cache", subscription_id=subscription_id)
        cache.delete(f"domain:{subscription_id}")
        cache.delete(f"domain:etag:{subscription_id}")
    else:
        logger.warning("Caching disabled, not deleting subscription", subscription=subscription_id)
