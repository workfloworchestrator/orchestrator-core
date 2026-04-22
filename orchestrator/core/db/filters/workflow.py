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
from sqlalchemy import BinaryExpression, select

from orchestrator.core.db import ProductTable, WorkflowTable
from orchestrator.core.db.filters import create_memoized_field_list, generic_filter_from_clauses
from orchestrator.core.db.filters.search_filters import default_inferred_column_clauses, filter_exact, inferred_filter
from orchestrator.core.utils.search_query import Node, WhereCondGenerator

logger = structlog.get_logger(__name__)


def make_product_clause(filter_generator: WhereCondGenerator) -> WhereCondGenerator:
    """The passed filter_generator takes a Node and returns a where clause acting on a ProductTable column."""

    def product_clause(node: Node) -> BinaryExpression:
        subq = (
            select(WorkflowTable.workflow_id)
            .join(WorkflowTable.products)
            .where(filter_generator(node))
            .scalar_subquery()
        )
        return WorkflowTable.workflow_id.in_(subq)

    return product_clause


WORKFLOW_TABLE_COLUMN_CLAUSES = default_inferred_column_clauses(WorkflowTable) | {
    "product": make_product_clause(inferred_filter(ProductTable.name)),
    "tag": make_product_clause(filter_exact(ProductTable.tag)),
}


workflow_filter_fields = create_memoized_field_list(WORKFLOW_TABLE_COLUMN_CLAUSES)
filter_workflows = generic_filter_from_clauses(WORKFLOW_TABLE_COLUMN_CLAUSES)
