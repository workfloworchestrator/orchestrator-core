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
from typing import Any, Optional, cast

from structlog import get_logger

from orchestrator.db.database import Database, transactional
from orchestrator.db.models import (  # noqa: F401
    EngineSettingsTable,
    FixedInputTable,
    ProcessStepTable,
    ProcessSubscriptionTable,
    ProcessTable,
    ProductBlockTable,
    ProductTable,
    ResourceTypeTable,
    SubscriptionCustomerDescriptionTable,
    SubscriptionInstanceRelationTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    SubscriptionTable,
    UtcTimestamp,
    UtcTimestampException,
    WorkflowTable,
)
from orchestrator.settings import AppSettings

logger = get_logger(__name__)


class WrappedDatabase:
    def __init__(self, wrappee: Optional[Database] = None) -> None:
        self.wrapped_database = wrappee

    def update(self, wrappee: Database) -> None:
        self.wrapped_database = wrappee
        logger.warning("Database object configured, all methods referencing `db` should work.")

    def __getattr__(self, attr: str) -> Any:
        if not isinstance(self.wrapped_database, Database):
            if "_" in attr:
                logger.warning("No database configured, but attempting to access class methods")
                return
            raise RuntimeWarning(
                "No database configured at this time. Please pass database configuration to OrchestratorCore base_settings"
            )

        return getattr(self.wrapped_database, attr)


# You need to pass a modified AppSettings class to the OrchestratorCore class to init the database correctly
wrapped_db = WrappedDatabase()
db = cast(Database, wrapped_db)


# The Global Database is set after calling this function
def init_database(settings: AppSettings) -> Database:
    wrapped_db.update(Database(settings.DATABASE_URI))
    return db


__all__ = [
    "transactional",
    "SubscriptionTable",
    "ProcessSubscriptionTable",
    "ProcessTable",
    "ProcessStepTable",
    "ProductTable",
    "ProductBlockTable",
    "SubscriptionInstanceRelationTable",
    "SubscriptionInstanceTable",
    "SubscriptionInstanceValueTable",
    "ResourceTypeTable",
    "FixedInputTable",
    "EngineSettingsTable",
    "WorkflowTable",
    "SubscriptionCustomerDescriptionTable",
    "UtcTimestamp",
    "UtcTimestampException",
    "db",
    "init_database",
]
