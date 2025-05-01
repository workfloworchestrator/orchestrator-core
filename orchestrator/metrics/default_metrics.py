import functools
from functools import partial

from prometheus_client import Gauge
from sqlalchemy import desc, func, select

from orchestrator.db import ProcessTable, WorkflowTable, db
from orchestrator.metrics.subscriptions import initialize_subscription_count_metrics


@functools.cache
def _get_active_tasks() -> list[dict]:
    """Get all active tasks.

    SELECT w.name, COUNT(*) FROM processes p
    JOIN workflows w ON p.workflow_id = w.workflow_id
    WHERE p.is_task = true
    GROUP BY w.name
    """
    task_count = func.count(ProcessTable.process_id).label("task_count")
    query = (
        db.session.query(WorkflowTable.name, task_count)
        .join(WorkflowTable)
        .where(ProcessTable.is_task)
        .group_by(WorkflowTable.name)
        .order_by(desc(task_count))
    )
    return query.all()


def count_active_tasks(task_name: str, first: bool) -> float:
    if first:
        _get_active_tasks.cache_clear()

    all_active_tasks = _get_active_tasks()

    total = sum(task_count[2] for task_count in all_active_tasks if task_count[1] == task_name)

    return float(total)


def initialize_task_count_metrics() -> None:
    query = select(WorkflowTable.name).where(WorkflowTable.target == "SYSTEM").distinct()
    all_tasks = db.session.execute(query).all()
    for index, result in enumerate(all_tasks):
        (task_name,) = result
        metric_name = f"active_{task_name}_process_count"
        active_tasks = Gauge(
            metric_name, namespace="wfo", documentation=f"Number of {task_name} tasks that have been processed"
        )
        first = index == 0
        active_tasks.set_function(partial(count_active_tasks, task_name=task_name, first=first))


def initialize_default_metrics() -> None:
    initialize_subscription_count_metrics()
    initialize_task_count_metrics()
