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
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from anyio import CancelScope, get_cancelled_exc_class
from redis.asyncio import Redis as AIORedis
from redis.asyncio.client import Pipeline, PubSub
from structlog import get_logger

from orchestrator.settings import app_settings
from orchestrator.utils.redis_client import (
    create_redis_asyncio_client,
    create_redis_client,
)

logger = get_logger(__name__)

cache = create_redis_client(app_settings.CACHE_URI)

ONE_WEEK = 3600 * 24 * 7


def default_get_subscription_id(data: Any) -> UUID:
    if hasattr(data, "subscription_id"):
        return data.subscription_id
    if isinstance(data, dict):
        return data["subscription_id"]
    return data


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
        self.client = create_redis_asyncio_client(redis_url)
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

        async def do_teardown() -> None:
            if not pubsub.subscribed:
                return

            await pubsub.unsubscribe(*channels)
            await pubsub.aclose()  # type: ignore[attr-defined]

        try:
            await pubsub.subscribe(*channels)
            yield pubsub
        except get_cancelled_exc_class():
            # https://anyio.readthedocs.io/en/3.x/cancellation.html#finalization
            with CancelScope(shield=True):
                await do_teardown()
            raise
        finally:
            await do_teardown()

    async def connect(self) -> None:
        # Execute a simple command to ensure we can establish a connection
        result = await self.client.ping()
        logger.debug("RedisBroadcast can connect to redis", ping_result=result)

    async def disconnect(self) -> None:
        logger.debug("Closing redis client")
        await self.client.aclose()  # type: ignore[attr-defined]
        logger.debug("Closed redis client")
