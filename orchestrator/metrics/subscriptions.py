from typing import Iterable

from prometheus_client import Metric
from prometheus_client.metrics_core import GaugeMetricFamily
from prometheus_client.registry import Collector
from pydantic import BaseModel
from sqlalchemy import desc, func

from orchestrator.db import ProductTable, SubscriptionTable, db
from orchestrator.types import SubscriptionLifecycle
from pydantic_forms.types import UUIDstr


class SubscriptionTableQueryResult(BaseModel):
    lifecycle_state: SubscriptionLifecycle
    customer_id: UUIDstr
    insync: bool
    product_name: str
    subscription_count: int


def _get_subscriptions() -> list[SubscriptionTableQueryResult]:
    """Query for getting all subscriptions.

    Equivalent to the following SQL statement:
    ```sql
    SELECT
        subscriptions.status                   AS lifecycle_state
        , subscriptions.customer_id
        , subscriptions.insync
        , products."name"                      AS product_name
        , Count(subscriptions.subscription_id) AS subscription_count
    FROM
      subscriptions
      JOIN products
        ON subscriptions.product_id = products.product_id
    GROUP BY  subscriptions.status
              , subscriptions.customer_id
              , insync
              , products."name"
    ;
    ```
    """
    subscription_count = func.count(SubscriptionTable.subscription_id).label("subscription_count")
    return (
        db.session.query(
            SubscriptionTable.status.label("lifecycle_state"),
            SubscriptionTable.customer_id,
            SubscriptionTable.insync,
            ProductTable.name.label("product_name"),
            subscription_count,
        )
        .outerjoin(ProductTable, ProductTable.product_id == SubscriptionTable.product_id)
        .group_by(
            SubscriptionTable.status,
            SubscriptionTable.customer_id,
            SubscriptionTable.insync,
            ProductTable.name,
        )
        .order_by(desc(subscription_count))
    ).all()


class SubscriptionCollector(Collector):
    """Collector for Subscriptions stored in the subscription database.

    This collector contains one gauge that contains the amount of subscriptions, per every combination of the labels
    that are defined:
        - Product name
        - Subscription lifecycle
        - Customer ID
        - `insync` state
    """

    def collect(self) -> Iterable[Metric]:
        subscriptions = GaugeMetricFamily(
            name="wfo_subscriptions_count",
            labels=[
                "product_name",
                "lifecycle_state",
                "customer_id",
                "insync",
            ],
            unit="count",
            documentation="Number of subscriptions per product, lifecycle state, customer, and in sync state.",
        )

        for row in _get_subscriptions():
            subscriptions.add_metric(
                [row.product_name, row.lifecycle_state, row.customer_id, str(row.insync)], row.subscription_count
            )

        return [subscriptions]
