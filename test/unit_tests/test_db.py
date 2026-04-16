import pytest
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

from orchestrator.db import ResourceTypeTable, SubscriptionTable, db
from orchestrator.db.helpers import get_postgres_version


@pytest.mark.parametrize(
    "create,check_absent",
    [
        pytest.param("aaa", "bbb", id="aaa"),
        pytest.param("bbb", "aaa", id="bbb"),
    ],
)
def test_autouse_fixture_rolls_back(create: str, check_absent: str):
    """Verify DB fixtures roll back between tests: each case commits a row and asserts the other's row is absent."""
    rt = ResourceTypeTable(resource_type=create, description=create)
    db.session.add(rt)
    db.session.commit()

    with pytest.raises(NoResultFound):
        db.session.scalars(select(ResourceTypeTable).where(ResourceTypeTable.resource_type == check_absent)).one()


def test_str_method():
    assert (
        str(SubscriptionTable())
        == "SubscriptionTable(subscription_id=None, description=None, status=None, product_id=None, customer_id=None, insync=None, start_date=None, end_date=None, note=None, version=None)"
    )


def test_get_postgres_version():
    pg_version = get_postgres_version()
    assert isinstance(pg_version, int)
    assert pg_version >= 13
