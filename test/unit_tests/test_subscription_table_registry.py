from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.orm import column_property

from orchestrator.app import OrchestratorCore
from orchestrator.db.models import SubscriptionTable


def test_register_table_copies_column_properties():
    """register_table should copy extra column_properties from custom to base."""

    class CustomSubscriptionTable(SubscriptionTable):
        extra_field = column_property(select(SubscriptionTable.description).scalar_subquery(), deferred=True)

    base_mapper = sa_inspect(SubscriptionTable)
    assert "extra_field" not in base_mapper.column_attrs

    OrchestratorCore.register_table(SubscriptionTable, CustomSubscriptionTable)

    assert "extra_field" in base_mapper.column_attrs

    # Clean up: remove injected property
    del base_mapper._props["extra_field"]


def test_register_table_does_not_overwrite_existing_columns():
    """register_table should not overwrite columns already on the base class."""
    base_mapper = sa_inspect(SubscriptionTable)
    original_description = base_mapper.column_attrs["description"]

    class CustomSubscriptionTable(SubscriptionTable):
        pass

    OrchestratorCore.register_table(SubscriptionTable, CustomSubscriptionTable)

    assert base_mapper.column_attrs["description"] is original_description
