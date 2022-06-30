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
from typing import Optional, Tuple, Union

from orchestrator.distlock.managers.memory_distlock_manager import Lock as MemoryLock
from orchestrator.distlock.managers.memory_distlock_manager import MemoryDistLockManager
from orchestrator.distlock.managers.redis_distlock_manager import Lock as RedisLock
from orchestrator.distlock.managers.redis_distlock_manager import RedisDistLockManager

DistLock = Union[MemoryLock, RedisLock]


class DistLockManager:
    """Provides an interface to lock access to a resource in a distributed system.

    The lock is advisory; it is up to the caller to respect it.

    Creating a lock is non-blocking, it succeeds or fails immediately.

    Locks are to be created with an expiration period after which the backend
    implementation must release it.
    """

    _backend: Union[MemoryDistLockManager, RedisDistLockManager]

    def __init__(self, enabled: bool, backend: Optional[str] = None, redis_address: Optional[Tuple[str, int]] = None):
        self.enabled = enabled
        self.connected = False
        if backend == "redis" and redis_address:
            self._backend = RedisDistLockManager(redis_address)
        else:
            self._backend = MemoryDistLockManager()

    async def connect_redis(self) -> None:
        if not self.connected:
            await self._backend.connect_redis()
            self.connected = True

    async def disconnect_redis(self) -> None:
        if self.connected:
            await self._backend.disconnect_redis()
            self.connected = False

    async def get_lock(self, resource: str, expiration_seconds: int) -> Optional[DistLock]:
        return await self._backend.get_lock(resource, expiration_seconds)

    async def release_lock(self, resource: DistLock) -> None:
        await self._backend.release_lock(resource)  # type: ignore

    def release_sync(self, resource: DistLock) -> None:
        self._backend.release_sync(resource)  # type: ignore
