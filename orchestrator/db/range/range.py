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

from http import HTTPStatus

import structlog

from orchestrator.api.error_handling import raise_status
from orchestrator.db.database import SearchQuery

logger = structlog.get_logger(__name__)


def apply_range_to_query(query: SearchQuery, offset: int, limit: int) -> SearchQuery:
    """Apply range to the SearchQuery.

    Args:
        query: The sql query to add offset and limit to.
        offset: the limit item in the list to get.
        limit: the amount of items to get with offset as start point.

    returns the query with offset and limit applied.
    """

    if offset is not None and limit:
        if offset >= offset + limit:
            msg = "range start must be lower than end"
            logger.exception(msg)
            raise_status(HTTPStatus.BAD_REQUEST, msg)
        query = query.offset(offset).limit(limit + 1)
    return query
