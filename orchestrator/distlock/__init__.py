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
from typing import Any, cast

from structlog import get_logger

from orchestrator.distlock.distlock_manager import DistLockManager
from orchestrator.settings import AppSettings

logger = get_logger(__name__)


async def empty_fn(*args: tuple, **kwargs: dict[str, Any]) -> None:
    return


class WrappedDistLockManager:
    def __init__(self, wrappee: DistLockManager | None = None) -> None:
        self.wrapped_distlock_manager = wrappee

    def update(self, wrappee: DistLockManager) -> None:
        self.wrapped_distlock_manager = wrappee
        logger.info("DistLockManager object configured, all methods referencing `distlock_manager` should work.")

    def __getattr__(self, attr: str) -> Any:
        if not isinstance(self.wrapped_distlock_manager, DistLockManager):
            if "_" in attr:
                logger.warning("No DistLockManager configured, but attempting to access class methods")
                return None
            raise RuntimeWarning(
                "No DistLockManager configured at this time. Please set ENABLE_DISTLOCK_MANAGER "
                "and DISTLOCK_BACKEND in OrchestratorCore base_settings"
            )
        if attr != "enabled" and not self.wrapped_distlock_manager.enabled:
            logger.warning("Distributed Locking is disabled, unable to access class methods")
            return empty_fn

        return getattr(self.wrapped_distlock_manager, attr)


wrapped_distlock_manager = WrappedDistLockManager()
distlock_manager = cast(DistLockManager, wrapped_distlock_manager)


# The Global DistLockManager is set after calling this function
def init_distlock_manager(settings: AppSettings) -> DistLockManager:
    wrapped_distlock_manager.update(
        DistLockManager(settings.ENABLE_DISTLOCK_MANAGER, settings.DISTLOCK_BACKEND, settings.CACHE_URI)
    )
    return distlock_manager


__all__ = [
    "distlock_manager",
    "init_distlock_manager",
]
