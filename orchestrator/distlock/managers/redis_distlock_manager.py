# Copyright 2019-2022 SURF.
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

from pydantic import RedisDsn
from redis import Redis
from redis.asyncio import Redis as AIORedis
from redis.asyncio.lock import Lock
from redis.exceptions import LockError
from redis.lock import Lock as SyncLock
from structlog import get_logger

from orchestrator.settings import app_settings

logger = get_logger(__name__)


class RedisDistLockManager:
    """Create Distributed Locks in Redis.

    https://redis.io/topics/distlock
    """

    namespace = "orchestrator:distlock"

    def __init__(self, redis_address: RedisDsn):
        self.redis_conn: AIORedis | None = None
        self.redis_address = redis_address

    async def connect_redis(self) -> None:
        self.redis_conn = AIORedis.from_url(str(self.redis_address))

    async def disconnect_redis(self) -> None:
        if self.redis_conn:
            await self.redis_conn.close()

    async def get_lock(self, resource: str, expiration_seconds: int) -> Lock | None:
        if not self.redis_conn:
            return None

        key = f"{self.namespace}:{resource}"
        try:
            lock: Lock = Lock(
                redis=self.redis_conn,
                name=key,
                timeout=float(expiration_seconds),
                blocking=False,
                thread_local=False,
            )
            if await lock.acquire():
                return lock
            # normal behavior (lock acquired by something else)
            return None
        except LockError:
            # Unexpected behavior, possibly a problem with Redis
            logger.Exception("Could not acquire lock for resource", resource=key)
            return None

    async def release_lock(self, lock: Lock) -> None:
        if not self.redis_conn:
            return

        try:
            await lock.release()
        except LockError:
            logger.Exception("Could not release lock for resource", resource=lock.name)

    # https://github.com/aio-libs/aioredis-py/issues/1273
    def release_sync(self, lock: Lock) -> None:
        redis_conn: Redis | None = None
        try:
            redis_conn = Redis.from_url(str(app_settings.CACHE_URI))
            sync_lock: SyncLock = SyncLock(
                redis=redis_conn,
                name=lock.name,  # type: ignore
                timeout=lock.timeout,
                blocking=False,
                thread_local=False,
            )
            sync_lock.local = lock.local
            sync_lock.release()
        except LockError:
            logger.Exception("Could not release lock for resource", resource=lock.name)
        finally:
            if redis_conn:
                redis_conn.close()


__all__ = [
    "RedisDistLockManager",
    "Lock",
]
