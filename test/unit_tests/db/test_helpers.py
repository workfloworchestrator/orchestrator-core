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

"""Tests for SQL compilation (to_sql_string) and Postgres version parsing (get_postgres_version)."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Integer, String, column, select, table

import orchestrator.db.helpers as helpers_module
from orchestrator.db.helpers import to_sql_string


@pytest.mark.parametrize(
    "stmt,expected_fragments",
    [
        pytest.param(
            select(column("id", Integer)).select_from(table("subscriptions")),
            ["subscriptions", "id"],
            id="simple-select",
        ),
        pytest.param(
            select(table("products", column("name", String)).c.name).where(
                table("products", column("status", String)).c.status == "active"
            ),
            ["active", "status"],
            id="where-literal",
        ),
    ],
)
def test_to_sql_string_renders_expected_fragments(stmt: object, expected_fragments: list[str]) -> None:
    result = to_sql_string(stmt)  # type: ignore[arg-type]
    assert isinstance(result, str)
    for fragment in expected_fragments:
        assert fragment in result


@pytest.fixture(autouse=True)
def _clear_version_cache() -> None:
    helpers_module.get_postgres_version.cache_clear()


@pytest.mark.parametrize(
    "version_num,expected_major",
    [
        pytest.param("120008", 12, id="pg12"),
        pytest.param("130007", 13, id="pg13"),
        pytest.param("140003", 14, id="pg14"),
        pytest.param("150001", 15, id="pg15"),
        pytest.param("160000", 16, id="pg16"),
    ],
)
def test_get_postgres_version_parses_correctly(version_num: str, expected_major: int) -> None:
    helpers_module.get_postgres_version.cache_clear()
    mock_db = MagicMock()
    mock_db.session.scalar.return_value = version_num
    with patch("orchestrator.db.helpers.db", mock_db):
        assert helpers_module.get_postgres_version() == expected_major


def test_get_postgres_version_returns_zero_on_value_error() -> None:
    mock_db = MagicMock()
    mock_db.session.scalar.return_value = "not_a_number"
    with patch("orchestrator.db.helpers.db", mock_db):
        assert helpers_module.get_postgres_version() == 0


def test_get_postgres_version_is_cached() -> None:
    mock_db = MagicMock()
    mock_db.session.scalar.return_value = "130007"
    with patch("orchestrator.db.helpers.db", mock_db):
        helpers_module.get_postgres_version()
        helpers_module.get_postgres_version()
    assert mock_db.session.scalar.call_count == 1
