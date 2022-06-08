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
from typing import Optional, Tuple

from pottery import AIORedlock
from pottery.exceptions import QuorumIsImpossible, ReleaseUnlockedLock
from redis.asyncio import Redis as AIORedis
from structlog import get_logger

logger = get_logger(__name__)


class RedisDistLockManager:
    """Create Distributed Locks in Redis.

    https://redis.io/topics/distlock
    """

    namespace = "orchestrator:distlock"

    def __init__(self, redis_address: Tuple[str, int]):
        self.redis_conn: Optional[AIORedis] = None
        self.redis_address = redis_address

    async def connect_redis(self) -> None:
        self.redis_conn = AIORedis(host=self.redis_address[0], port=self.redis_address[1])

    async def disconnect_redis(self) -> None:
        if self.redis_conn:
            await self.redis_conn.close()

    async def get_lock(self, resource: str, expiration_seconds: int) -> Optional[AIORedlock]:
        if not self.redis_conn:
            return None

        key = f"{self.namespace}:{resource}"
        try:
            lock: AIORedlock = AIORedlock(
                key=key,
                masters={self.redis_conn},
                raise_on_redis_errors=True,
                auto_release_time=float(expiration_seconds),
            )
            if await lock.acquire(blocking=False, raise_on_redis_errors=True):
                return lock
            else:
                # normal behavior (lock acquired by something else)
                return None
        except QuorumIsImpossible:
            # Unexpected behavior, possibly a problem with Redis
            logger.Exception("Could not acquire lock for resource", resource=key)
            return None

    async def release_lock(self, lock: AIORedlock) -> None:
        if not self.redis_conn:
            return None

        try:
            await lock.release(raise_on_redis_errors=True)
        except ReleaseUnlockedLock:
            logger.Exception("Could not release lock for resource", resource=lock.key)


__all__ = [
    "RedisDistLockManager",
    "AIORedlock",
]
