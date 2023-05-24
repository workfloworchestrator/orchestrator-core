from orchestrator.db import ProcessTable
from orchestrator.db.sorting.sorting import generic_sort

VALID_SORT_KEY_MAP = {
    "creator": "created_by",
    "started": "started_at",
    "status": "last_status",
    "assignee": "assignee",
    "modified": "last_modified_at",
    "workflow": "workflow",
}

sort_processes = generic_sort(VALID_SORT_KEY_MAP, ProcessTable)
