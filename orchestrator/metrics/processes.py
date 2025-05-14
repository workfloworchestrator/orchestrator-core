from typing import Iterable

from prometheus_client.metrics_core import GaugeMetricFamily, Metric
from prometheus_client.registry import Collector
from pydantic import BaseModel
from sqlalchemy import desc, func

from orchestrator.db import ProcessTable, ProductTable, SubscriptionTable, WorkflowTable, db
from orchestrator.db.models import ProcessSubscriptionTable
from orchestrator.targets import Target
from orchestrator.workflow import ProcessStatus
from pydantic_forms.types import UUIDstr


class ProcessTableQueryResult(BaseModel):
    workflow_name: str
    customer_id: UUIDstr
    workflow_target: Target
    last_status: ProcessStatus
    created_by: str
    is_task: bool
    product_name: str
    total_runtime: float
    process_count: int


def _get_processes() -> list[ProcessTableQueryResult]:
    """Query for getting all processes.

    Equivalent to the following SQL statement:
    ```sql
    SELECT
      workflows."name"                                                                          AS workflow_name
      , subscriptions.customer_id
      , workflows.target                                                                        AS workflow_target
      , processes.last_status
      , processes.created_by
      , processes.is_task
      , products."name"                                                                         AS product_name
      , Coalesce(Sum(Extract(EPOCH FROM processes.last_modified_at - processes.started_at)), 0) AS total_runtime
      , Count(workflows."name")                                                                 AS process_count
    FROM
      processes
    JOIN workflows
      ON processes.workflow_id = workflows.workflow_id
    JOIN processes_subscriptions
      ON processes.pid = processes_subscriptions.pid
    JOIN subscriptions
      ON processes_subscriptions.subscription_id = subscriptions.subscription_id
    JOIN products
      ON subscriptions.product_id = products.product_id
    GROUP BY
      workflows."name"
      , subscriptions.customer_id
      , workflows.target
      , processes.last_status
      , processes.created_by
      , processes.is_task
      , products."name"
    ;
    ```
    """
    process_count = func.count(WorkflowTable.name).label("process_count")
    total_process_time = func.coalesce(
        func.sum(func.extract("epoch", (ProcessTable.last_modified_at - ProcessTable.started_at))), 0
    ).label("total_runtime")
    return (
        db.session.query(
            ProcessTable.last_status,
            ProcessTable.created_by,
            ProcessTable.is_task,
            ProductTable.name.label("product_name"),
            WorkflowTable.name.label("workflow_name"),
            SubscriptionTable.customer_id,
            WorkflowTable.target.label("workflow_target"),
            process_count,
            total_process_time,
        )
        .join(WorkflowTable, WorkflowTable.workflow_id == ProcessTable.workflow_id)
        .join(ProcessSubscriptionTable, ProcessSubscriptionTable.process_id == ProcessTable.process_id)
        .join(SubscriptionTable, SubscriptionTable.subscription_id == ProcessSubscriptionTable.subscription_id)
        .join(ProductTable, ProductTable.product_id == SubscriptionTable.product_id)
        .group_by(
            ProcessTable.last_status,
            ProcessTable.created_by,
            ProcessTable.is_task,
            ProductTable.name,
            WorkflowTable.name,
            SubscriptionTable.customer_id,
            WorkflowTable.target,
        )
        .order_by(desc(process_count))
    ).all()


class ProcessCollector(Collector):
    """Collector that contains two Prometheus gauges with process counts and total runtime.

    These gauges contain the amount of processes, and the total runtime in seconds, per every combination of the labels
    that are defined:
        - Process last status
        - Process created by
        - Process is task
        - Product name
        - Workflow name
        - Customer ID
        - Workflow target
    """

    def collect(self) -> Iterable[Metric]:
        label_names = [
            "last_status",
            "created_by",
            "is_task",
            "product_name",
            "workflow_name",
            "customer_id",
            "workflow_target",
        ]
        process_counts = GaugeMetricFamily(
            "wfo_process_count",
            labels=label_names,
            unit="count",
            documentation="Number of processes per status, creator, task, product, workflow, customer, and target.",
        )
        process_seconds_total = GaugeMetricFamily(
            "wfo_process_seconds_total",
            labels=label_names,
            unit="count",
            documentation="Total time spent on processes in seconds.",
        )

        for row in _get_processes():
            label_values = [
                row.last_status,
                str(row.created_by),
                str(row.is_task),
                row.product_name,
                row.workflow_name,
                row.customer_id,
                row.workflow_target,
            ]

            process_counts.add_metric(label_values, row.process_count)
            process_seconds_total.add_metric(label_values, row.total_runtime)

        return [process_counts, process_seconds_total]
