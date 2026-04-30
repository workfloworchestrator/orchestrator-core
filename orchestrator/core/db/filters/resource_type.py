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

import structlog
from sqlalchemy import BinaryExpression

from orchestrator.core.db import ProductBlockTable, ResourceTypeTable
from orchestrator.core.db.filters import create_memoized_field_list, generic_filter_from_clauses
from orchestrator.core.db.filters.search_filters import default_inferred_column_clauses, node_to_str_val
from orchestrator.core.utils.search_query import Node

logger = structlog.get_logger(__name__)


def product_blocks_clause(node: Node) -> BinaryExpression:
    return ResourceTypeTable.product_blocks.any(ProductBlockTable.name.ilike(node_to_str_val(node)))


RESOURCE_TYPE_TABLE_COLUMN_CLAUSES = default_inferred_column_clauses(ResourceTypeTable) | {
    "product_block": product_blocks_clause,
}

resource_type_filter_fields = create_memoized_field_list(RESOURCE_TYPE_TABLE_COLUMN_CLAUSES)
filter_resource_types = generic_filter_from_clauses(RESOURCE_TYPE_TABLE_COLUMN_CLAUSES)
