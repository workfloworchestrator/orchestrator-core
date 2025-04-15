import functools
from functools import partial

from prometheus_client import Gauge
from sqlalchemy import select, func, desc

from orchestrator.db import db, SubscriptionTable, ProductTable

@functools.cache
def _get_active_subscriptions():
    print("Execute query!")
    subscription_count = func.count(SubscriptionTable.subscription_id).label("subscription_count")
    query = (
        db.session.query(
            ProductTable.product_id,
            ProductTable.name,
            ProductTable.product_type,
            subscription_count
        )
        .outerjoin(SubscriptionTable, ProductTable.product_id == SubscriptionTable.product_id)
        .group_by(ProductTable.product_id)
        .order_by(desc(subscription_count))
    )
    return query.all()


def count_active_subscriptions(product_type: str, first: bool) -> float:
    print(f"***** {product_type} {first}")
    if first:
        _get_active_subscriptions.cache_clear()

    results = _get_active_subscriptions()

    total = sum(result[3] for result in results if result[2] == product_type)
    print(total)

    return float(total)

    # return db.session.scalar(select(func.count()).select_from(SubscriptionTable))


def initialize_product_count_metrics():
    query = select(ProductTable.product_type).distinct()
    results = db.session.execute(query).all()
    for index, result in enumerate(results):
        product_type, = result
        name = f"active_{product_type.lower()}_subscriptions_count"
        active_subscriptions = Gauge(name,
                                     namespace="wfo",
                                     # labelnames=[product_type],
                                     documentation=f"Number of {product_type} subscriptions")
        first = index == 0  # Trigger to re-execute query
        active_subscriptions.set_function(partial(count_active_subscriptions, product_type=product_type, first=first))

    print(results)


def initialize_metrics():
    initialize_product_count_metrics()