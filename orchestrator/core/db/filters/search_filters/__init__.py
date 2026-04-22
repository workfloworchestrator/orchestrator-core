# Copyright 2019-2026 SURF, GÉANT.
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

from sqlalchemy import inspect

from orchestrator.core.db.database import BaseModel
from orchestrator.core.db.filters.search_filters.inferred_filter import filter_exact, inferred_filter, node_to_str_val

__all__ = ["inferred_filter", "default_inferred_column_clauses", "node_to_str_val", "filter_exact"]

from orchestrator.core.utils.search_query import WhereCondGenerator


def default_inferred_column_clauses(table: type[BaseModel]) -> dict[str, WhereCondGenerator]:
    return {key: inferred_filter(column) for key, column in getattr(inspect(table), "columns", {}).items()}
