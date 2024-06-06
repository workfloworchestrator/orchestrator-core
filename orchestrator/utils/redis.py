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
import functools
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from os import getenv
from typing import Any, Callable
from uuid import UUID

from redis import Redis
from redis.asyncio import Redis as AIORedis
from redis.asyncio.client import Pipeline, PubSub
from structlog import get_logger

from orchestrator.services.subscriptions import _generate_etag
from orchestrator.settings import app_settings
from orchestrator.utils.json import PY_JSON_TYPES, json_dumps, json_loads

logger = get_logger(__name__)

cache = Redis.from_url(str(app_settings.CACHE_URI))

ONE_WEEK = 3600 * 24 * 7


def caching_models_enabled() -> bool:
    return getenv("AIOCACHE_DISABLE", "0") == "0" and app_settings.CACHE_DOMAIN_MODELS


def to_redis(subscription: dict[str, Any]) -> str | None:
    if caching_models_enabled():
        logger.info("Setting cache for subscription", subscription=subscription["subscription_id"])
        etag = _generate_etag(subscription)
        cache.set(f"domain:{subscription['subscription_id']}", json_dumps(subscription), ex=ONE_WEEK)
        cache.set(f"domain:etag:{subscription['subscription_id']}", etag, ex=ONE_WEEK)
        return etag

    logger.warning("Caching disabled, not caching subscription", subscription=subscription["subscription_id"])
    return None


def from_redis(subscription_id: UUID) -> tuple[PY_JSON_TYPES, str] | None:
    log = logger.bind(subscription_id=subscription_id)
    if caching_models_enabled():
        log.debug("Try to retrieve subscription from cache")
        obj = cache.get(f"domain:{subscription_id}")
        etag = cache.get(f"domain:etag:{subscription_id}")
        if obj and etag:
            log.info("Retrieved subscription from cache")
            return json_loads(obj), etag.decode("utf-8")
        log.info("Subscription not found in cache")
        return None
    log.warning("Caching disabled, not loading subscription")
    return None


def delete_from_redis(subscription_id: UUID) -> None:
    if caching_models_enabled():
        logger.info("Deleting subscription object from cache", subscription_id=subscription_id)
        cache.delete(f"domain:{subscription_id}")
        cache.delete(f"domain:etag:{subscription_id}")
    else:
        logger.warning("Caching disabled, not deleting subscription", subscription=subscription_id)


def default_get_subscription_id(data: Any) -> UUID:
    if hasattr(data, "subscription_id"):
        return data.subscription_id
    if isinstance(data, dict):
        return data["subscription_id"]
    return data


def delete_subscription_from_redis(
    extract_fn: Callable[..., UUID] = default_get_subscription_id
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def _delete_subscription_from_redis(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: tuple, **kwargs: dict[str, Any]) -> Any:
            data = await func(*args, **kwargs)
            key = extract_fn(data)
            delete_from_redis(key)
            return data

        return wrapper

    return _delete_subscription_from_redis


async def delete_keys_matching_pattern(_cache: AIORedis, pattern: str, chunksize: int = 5000) -> int:
    """Delete all keys matching the given pattern.

    Usage:
        >>> await delete_keys_matching_pattern("orchestrator:foo:*")  # doctest:+SKIP
    """
    deleted = 0

    async def fetch(_cursor: int = 0) -> tuple[int, list[bytes]]:
        return await _cache.scan(cursor=_cursor, match=pattern, count=chunksize)

    cursor, keys = await fetch()
    while keys or cursor != 0:
        if keys:
            deleted += await _cache.delete(*keys)
        cursor, keys = await fetch(_cursor=cursor)

    logger.debug("Deleted keys matching pattern", pattern=pattern, deleted=deleted)
    return deleted


class RedisBroadcast:
    """Small wrapper around redis.asyncio.Redis used by websocket broadcasting.

    Note:
        redis.asyncio.Redis.from_url() returns a client which maintains a ConnectionPool.
        This instance is thread-safe and does not create connections until needed.
        However, you cannot instantiate this in one asyncio event loop and use it in
        another event loop, as the created connections in the pool will then only
        be usable by the loop they were created in.
    """

    client: AIORedis

    def __init__(self, redis_url: str):
        self.client = AIORedis.from_url(redis_url)
        self.redis_url = redis_url

    @asynccontextmanager
    async def pipeline(self) -> AsyncGenerator[Pipeline, None]:
        """Context to prepare a pipeline object for issueing multiple commands, such as .publish().

        Automatically executes the pipeline afterwards (unless there was an exception).
        """
        async with self.client.pipeline() as pipe:
            yield pipe
            await pipe.execute()

    @asynccontextmanager
    async def subscriber(self, *channels: str) -> AsyncGenerator[PubSub, None]:
        """Context to subscribe to one or more channels.

        Automatically unsubscribes and releases the connection afterwards.
        """
        pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        try:
            await pubsub.subscribe(*channels)
            yield pubsub
        finally:
            await pubsub.unsubscribe(*channels)
            await pubsub.aclose()  # type: ignore[attr-defined]

    async def connect(self) -> None:
        # Execute a simple command to ensure we can establish a connection
        result = await self.client.ping()
        logger.debug("RedisBroadcast can connect to redis", ping_result=result)

    async def disconnect(self) -> None:
        logger.debug("Closing redis client")
        await self.client.aclose()  # type: ignore[attr-defined]
        logger.debug("Closed redis client")
