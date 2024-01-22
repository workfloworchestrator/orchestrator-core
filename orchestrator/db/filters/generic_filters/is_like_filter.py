# Copyright 2019-2023 SURF.
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


from collections.abc import Callable

from sqlalchemy import ColumnClause, String, cast

from orchestrator.db.filters.filters import QueryType


def generic_is_like_filter(field: ColumnClause) -> Callable[[QueryType, str], QueryType]:
    def like_filter(query: QueryType, value: str) -> QueryType:
        return query.filter(cast(field, String).ilike("%" + value + "%"))

    return like_filter
