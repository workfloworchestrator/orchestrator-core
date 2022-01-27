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

from aioredlock import Aioredlock, Lock, LockAcquiringError, LockError
from structlog import get_logger

logger = get_logger(__name__)


class RedisDistLockManager:
    """Create Distributed Locks in Redis.

    https://redis.io/topics/distlock
    """

    namespace = "orchestrator:distlock"

    def __init__(self, redis_address: Tuple[str, int]):
        self.redis_distlock: Optional[Aioredlock] = None
        self.redis_address = redis_address

    async def connect_redis(self) -> None:
        self.redis_distlock = Aioredlock([self.redis_address])

    async def disconnect_redis(self) -> None:
        if self.redis_distlock:
            await self.redis_distlock.destroy()

    async def get_lock(self, resource: str, expiration_seconds: int) -> Optional[Lock]:
        if not self.redis_distlock:
            return None

        key = f"{self.namespace}:{resource}"
        try:
            return await self.redis_distlock.lock(key, expiration_seconds)
        except LockAcquiringError:
            # normal behavior (lock acquired by something else)
            return None
        except LockError:
            # Unexpected behavior, possibly a problem with Redis
            logger.Exception("Could not acquire lock for resource", resource=key)
            return None

    async def release_lock(self, lock: Lock) -> None:
        if not self.redis_distlock:
            return None

        try:
            await self.redis_distlock.unlock(lock)
        except LockError:
            logger.Exception("Could not release lock for resource", resource=lock.resource)


__all__ = [
    "RedisDistLockManager",
    "Lock",
]
