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

from sqlalchemy.inspection import inspect

from orchestrator.core.db import WorkflowTable
from orchestrator.core.db.filters import create_memoized_field_list
from orchestrator.core.db.sorting import generic_column_sort, generic_sort
from orchestrator.core.utils.helpers import to_camel

WORKFLOW_SORT_FUNCTIONS_BY_COLUMN = {
    to_camel(key): generic_column_sort(value, WorkflowTable) for key, value in inspect(WorkflowTable).columns.items()
}

workflow_sort_fields = create_memoized_field_list(WORKFLOW_SORT_FUNCTIONS_BY_COLUMN)
sort_workflows = generic_sort(WORKFLOW_SORT_FUNCTIONS_BY_COLUMN)
