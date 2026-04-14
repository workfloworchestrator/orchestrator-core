# Copyright 2019-2020 SURF.
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

"""Tests for _register_pool_events: checkin listener registration and rollback-on-checkin behaviour."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine

from orchestrator.db.database import _register_pool_events


def _sqlite_engine():
    """Return a fresh in-memory SQLite engine with no pool events attached."""
    return create_engine("sqlite:///:memory:")


def _get_checkin_listeners(engine):
    """Return the list of registered checkin listeners on the engine's pool."""
    return list(engine.pool.dispatch.checkin)


# --- listener registration ---


def test_register_pool_events_adds_exactly_one_checkin_listener() -> None:
    engine = _sqlite_engine()
    assert _get_checkin_listeners(engine) == [], "precondition: no listeners before registration"

    _register_pool_events(engine)

    listeners = _get_checkin_listeners(engine)
    assert len(listeners) == 1


def test_register_pool_events_listener_is_named_on_checkin() -> None:
    engine = _sqlite_engine()
    _register_pool_events(engine)

    (listener,) = _get_checkin_listeners(engine)
    assert listener.__name__ == "_on_checkin"


# --- handler behaviour ---


def _get_handler(engine):
    """Register pool events and return the single checkin handler."""
    _register_pool_events(engine)
    (handler,) = _get_checkin_listeners(engine)
    return handler


def test_on_checkin_calls_rollback_on_dbapi_connection() -> None:
    handler = _get_handler(_sqlite_engine())

    dbapi_connection = MagicMock()
    connection_record = MagicMock()

    handler(dbapi_connection, connection_record)

    dbapi_connection.rollback.assert_called_once_with()


def test_on_checkin_ignores_connection_record_argument() -> None:
    """The handler must not interact with connection_record in any way."""
    handler = _get_handler(_sqlite_engine())

    dbapi_connection = MagicMock()
    connection_record = MagicMock()

    handler(dbapi_connection, connection_record)

    connection_record.assert_not_called()


# --- exception swallowing ---


@pytest.mark.parametrize(
    "exc_type",
    [
        pytest.param(Exception, id="base-exception"),
        pytest.param(RuntimeError, id="runtime-error"),
        pytest.param(OSError, id="os-error"),
        pytest.param(ValueError, id="value-error"),
    ],
)
def test_on_checkin_swallows_rollback_exception(exc_type: type[Exception]) -> None:
    handler = _get_handler(_sqlite_engine())

    dbapi_connection = MagicMock()
    dbapi_connection.rollback.side_effect = exc_type("db gone")
    connection_record = MagicMock()

    # Must not propagate
    handler(dbapi_connection, connection_record)
