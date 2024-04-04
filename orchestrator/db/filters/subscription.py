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
import structlog

from orchestrator.api.helpers import add_subscription_search_query_filter
from orchestrator.db import ProductTable, SubscriptionTable
from orchestrator.db.filters import create_memoized_field_list, generic_filter_from_clauses
from orchestrator.db.filters.search_filters import default_inferred_column_clauses, inferred_filter
from orchestrator.db.filters.search_filters.inferred_filter import filter_exact

logger = structlog.get_logger(__name__)


SUBSCRIPTION_TABLE_COLUMN_CLAUSES = default_inferred_column_clauses(SubscriptionTable) | {
    "product": inferred_filter(ProductTable.name),
    "tag": filter_exact(ProductTable.tag),
}

subscription_filter_fields = create_memoized_field_list(SUBSCRIPTION_TABLE_COLUMN_CLAUSES)
filter_subscriptions = generic_filter_from_clauses(SUBSCRIPTION_TABLE_COLUMN_CLAUSES)

filter_by_query_string = add_subscription_search_query_filter
