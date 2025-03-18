from uuid import UUID

from sqlalchemy import select

from orchestrator.db import db
from orchestrator.db.models import SubscriptionInstanceAsJsonFunction


def get_subscription_instance_dict(subscription_instance_id: UUID) -> dict:
    """Query the subscription instance as aggregated JSONB and returns it as a dict.

    Note: all values are returned as lists and have to be transformed by the caller.
    It was attempted to do this in the DB query but this gave worse performance.
    """
    return db.session.execute(select(SubscriptionInstanceAsJsonFunction(subscription_instance_id))).scalar_one()
