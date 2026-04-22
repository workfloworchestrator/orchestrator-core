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

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.orm import column_property

from orchestrator.app import OrchestratorCore
from orchestrator.db.models import SubscriptionTable


@pytest.fixture()
def _cleanup_extra_field():
    """Remove injected extra_field from SubscriptionTable mapper after test."""
    yield
    base_mapper = sa_inspect(SubscriptionTable)
    base_mapper._props.pop("extra_field", None)


@pytest.mark.usefixtures("_cleanup_extra_field")
def test_register_table_copies_column_properties():
    """register_table should copy extra column_properties from custom to base."""

    class CustomSubscriptionTable(SubscriptionTable):
        extra_field = column_property(select(SubscriptionTable.description).scalar_subquery(), deferred=True)

    base_mapper = sa_inspect(SubscriptionTable)
    assert "extra_field" not in base_mapper.column_attrs

    OrchestratorCore.register_table(SubscriptionTable, CustomSubscriptionTable)

    assert "extra_field" in base_mapper.column_attrs


@pytest.mark.usefixtures("_cleanup_extra_field")
def test_register_table_is_idempotent():
    """Calling register_table twice with the same class should not raise."""

    class CustomSubscriptionTable(SubscriptionTable):
        extra_field = column_property(select(SubscriptionTable.description).scalar_subquery(), deferred=True)

    OrchestratorCore.register_table(SubscriptionTable, CustomSubscriptionTable)
    OrchestratorCore.register_table(SubscriptionTable, CustomSubscriptionTable)

    base_mapper = sa_inspect(SubscriptionTable)
    assert "extra_field" in base_mapper.column_attrs


@pytest.mark.usefixtures("_cleanup_extra_field")
def test_register_table_column_accessible_in_query(generic_subscription_1):
    """After register_table, custom column_properties should be accessible in queries."""
    from orchestrator.db import db

    class CustomSubscriptionTable(SubscriptionTable):
        extra_field = column_property(
            select(SubscriptionTable.description).correlate(SubscriptionTable).scalar_subquery(), deferred=True
        )

    OrchestratorCore.register_table(SubscriptionTable, CustomSubscriptionTable)

    result = db.session.scalars(select(SubscriptionTable)).first()
    assert result is not None
    assert result.extra_field is not None
