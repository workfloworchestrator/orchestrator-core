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
import asyncio
from threading import Lock, Thread
from time import sleep, time
from typing import Optional

from structlog import get_logger

logger = get_logger(__name__)


class MemoryDistLockManager(Thread):
    """Create Distributed Locks in memory.

    This is the default implementation when not using Redis.

    Locks are limited to the current process, therefore this implementation should not be used
    in a setup with multiple gunicorn workers.
    """

    manager_lock: Lock = Lock()
    locks: dict[str, tuple[Lock, float]] = {}

    def __init__(self) -> None:
        super().__init__()
        self.daemon = True
        self.name = "MemoryDistLockExpirationThread"
        self.start()

    async def connect_redis(self) -> None:
        pass

    async def disconnect_redis(self) -> None:
        pass

    async def get_lock(
        self, resource: str, expiration_seconds: int
    ) -> Optional[Lock]:  # https://github.com/python/cpython/issues/114315
        with self.manager_lock:
            resource_lock, expire_at = self.locks.get(resource, (Lock(), time() + expiration_seconds))
            if not resource_lock.acquire(blocking=False):
                logger.debug("Resource is already locked", resource=resource, expire_at=expire_at)
                return None
            logger.debug("Successfully locked resource", resource=resource, expire_at=expire_at)
            self.locks[resource] = resource_lock, expire_at
            return resource_lock

    async def release_lock(self, lock: Lock) -> None:
        with self.manager_lock:
            lock.release()
            for resource, (resource_lock, _) in self.locks.items():
                if lock is resource_lock:
                    name = resource
                    break
            del self.locks[name]
            logger.debug("Successfully unlocked resource", resource=name)

    def release_sync(self, lock: Lock) -> None:
        asyncio.run(self.release_lock(lock))

    def run(self) -> None:
        while True:
            with self.manager_lock:
                timestamp = time()
                for resource, (resource_lock, expire_at) in list(self.locks.items()):
                    if expire_at > timestamp:
                        continue
                    resource_lock.release()
                    del self.locks[resource]
                    logger.debug("Successfully unlocked expired resource", resource=resource, expire_at=expire_at)
            sleep(0.1)


__all__ = [
    "MemoryDistLockManager",
    "Lock",
]
