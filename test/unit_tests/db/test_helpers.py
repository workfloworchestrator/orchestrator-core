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

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Integer, String, column, select, table

import orchestrator.db.helpers as helpers_module
from orchestrator.db.helpers import to_sql_string


class TestToSqlString:
    def test_simple_select_returns_string(self):
        stmt = select(column("id", Integer)).select_from(table("subscriptions"))
        result = to_sql_string(stmt)
        assert isinstance(result, str)

    def test_simple_select_contains_table_name(self):
        stmt = select(column("id", Integer)).select_from(table("subscriptions"))
        result = to_sql_string(stmt)
        assert "subscriptions" in result

    def test_simple_select_contains_column_name(self):
        stmt = select(column("id", Integer)).select_from(table("subscriptions"))
        result = to_sql_string(stmt)
        assert "id" in result

    def test_select_with_where_clause_renders_literal(self):
        t = table("products", column("name", String), column("status", String))
        stmt = select(t.c.name).where(t.c.status == "active")
        result = to_sql_string(stmt)
        assert "active" in result
        assert "status" in result

    def test_select_with_integer_literal(self):
        t = table("items", column("count", Integer))
        stmt = select(t.c.count).where(t.c.count > 5)
        result = to_sql_string(stmt)
        assert "5" in result

    def test_select_star_style(self):
        t = table("workflows", column("workflow_id"), column("name"))
        stmt = select(t.c.workflow_id, t.c.name)
        result = to_sql_string(stmt)
        assert "workflows" in result
        assert "workflow_id" in result
        assert "name" in result

    def test_uses_postgresql_dialect(self):
        """to_sql_string should produce PostgreSQL-flavoured SQL."""
        t = table("items", column("val", String))
        stmt = select(t.c.val).where(t.c.val == "test")
        result = to_sql_string(stmt)
        # PostgreSQL uses single quotes for string literals
        assert "'" in result


class TestGetPostgresVersion:
    def setup_method(self):
        helpers_module.get_postgres_version.cache_clear()

    def teardown_method(self):
        helpers_module.get_postgres_version.cache_clear()

    def test_returns_zero_on_value_error(self):
        mock_db = MagicMock()
        mock_db.session.scalar.return_value = "not_a_number"
        with patch("orchestrator.db.helpers.db", mock_db):
            result = helpers_module.get_postgres_version()
        assert result == 0

    def test_logs_error_on_value_error(self):
        mock_db = MagicMock()
        mock_db.session.scalar.return_value = "bad_value"
        with patch("orchestrator.db.helpers.db", mock_db):
            with patch("orchestrator.db.helpers.logger") as mock_logger:
                helpers_module.get_postgres_version()
        mock_logger.error.assert_called_once()

    def test_result_is_cached(self):
        mock_db = MagicMock()
        mock_db.session.scalar.return_value = "130007"
        with patch("orchestrator.db.helpers.db", mock_db):
            helpers_module.get_postgres_version()
            helpers_module.get_postgres_version()
        # scalar should only be called once due to cache
        assert mock_db.session.scalar.call_count == 1

    @pytest.mark.parametrize(
        "version_num, expected_major",
        [
            ("120008", 12),
            ("130007", 13),
            ("140003", 14),
            ("150001", 15),
            ("160000", 16),
        ],
        ids=["pg12", "pg13", "pg14", "pg15", "pg16"],
    )
    def test_parametrized_version_parsing(self, version_num: str, expected_major: int):
        helpers_module.get_postgres_version.cache_clear()
        mock_db = MagicMock()
        mock_db.session.scalar.return_value = version_num
        with patch("orchestrator.db.helpers.db", mock_db):
            result = helpers_module.get_postgres_version()
        assert result == expected_major
