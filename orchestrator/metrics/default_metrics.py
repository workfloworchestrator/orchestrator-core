import functools
from functools import partial

from prometheus_client import Gauge
from sqlalchemy import desc, func, select

from orchestrator.db import ProcessTable, ProductTable, SubscriptionTable, WorkflowTable, db


@functools.cache
def _get_active_subscriptions():
    subscription_count = func.count(SubscriptionTable.subscription_id).label("subscription_count")
    query = (
        db.session.query(ProductTable.product_id, ProductTable.name, ProductTable.product_type, subscription_count)
        .outerjoin(SubscriptionTable, ProductTable.product_id == SubscriptionTable.product_id)
        .group_by(ProductTable.product_id)
        .order_by(desc(subscription_count))
    )
    return query.all()


def count_active_subscriptions(product_type: str, first: bool) -> float:
    if first:
        _get_active_subscriptions.cache_clear()

    results = _get_active_subscriptions()

    total = sum(result[3] for result in results if result[2] == product_type)

    return float(total)

    # return db.session.scalar(select(func.count()).select_from(SubscriptionTable))


@functools.cache
def _get_active_tasks():
    """SELECT w.name, COUNT(*) FROM processes p
    JOIN workflows w ON p.workflow_id = w.workflow_id
    WHERE p.is_task = true
    GROUP BY w.name
    """
    task_count = func.count(ProcessTable.process_id).label("task_count")
    query = (
        db.session.query(WorkflowTable.name, task_count)
        .join(WorkflowTable)
        .where(ProcessTable.is_task == True)
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


def initialize_product_count_metrics():
    query = select(ProductTable.product_type).distinct()
    results = db.session.execute(query).all()
    for index, result in enumerate(results):
        (product_type,) = result
        name = f"active_{product_type.lower()}_subscriptions_count"
        active_subscriptions = Gauge(
            name,
            namespace="wfo",
            # labelnames=[product_type],
            documentation=f"Number of {product_type} subscriptions",
        )
        first = index == 0  # Trigger to re-execute query
        active_subscriptions.set_function(partial(count_active_subscriptions, product_type=product_type, first=first))

    print(results)


def initialize_task_count_metrics():
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

    print(all_tasks)


def initialize_metrics():
    initialize_product_count_metrics()
    initialize_task_count_metrics()
