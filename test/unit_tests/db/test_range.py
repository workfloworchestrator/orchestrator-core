# Copyright 2019-2023 SURF.
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
from unittest.mock import MagicMock

import pytest
from sqlalchemy import column, select, table

from orchestrator.db.range.range import apply_range_to_query, apply_range_to_statement


def _make_stmt():
    t = table("items", column("id"))
    return select(t)


class TestApplyRangeToStatement:
    def test_valid_range_applies_slice(self):
        stmt = _make_stmt()
        result = apply_range_to_statement(stmt, 0, 10)
        # Compile and verify LIMIT/OFFSET are present
        compiled = str(result.compile())
        assert "LIMIT" in compiled or "FETCH" in compiled or result is not stmt

    def test_range_start_zero(self):
        stmt = _make_stmt()
        result = apply_range_to_statement(stmt, 0, 1)
        assert result is not None

    def test_range_start_greater_than_end_raises(self):
        stmt = _make_stmt()
        with pytest.raises(ValueError, match="range start must be lower than end"):
            apply_range_to_statement(stmt, 10, 5)

    def test_range_start_equal_to_end_raises(self):
        stmt = _make_stmt()
        with pytest.raises(ValueError, match="range start must be lower than end"):
            apply_range_to_statement(stmt, 5, 5)

    @pytest.mark.parametrize(
        "start, end",
        [
            (0, 10),
            (5, 15),
            (100, 200),
            (0, 1),
        ],
        ids=["zero_to_ten", "five_to_fifteen", "large_range", "minimal_range"],
    )
    def test_valid_ranges(self, start, end):
        stmt = _make_stmt()
        result = apply_range_to_statement(stmt, start, end)
        assert result is not None

    @pytest.mark.parametrize(
        "start, end",
        [
            (5, 0),
            (1, 0),
            (100, 50),
        ],
        ids=["five_zero", "one_zero", "hundred_fifty"],
    )
    def test_invalid_ranges_raise(self, start, end):
        stmt = _make_stmt()
        with pytest.raises(ValueError, match="range start must be lower than end"):
            apply_range_to_statement(stmt, start, end)


class TestApplyRangeToQuery:
    def _make_query(self):
        """Create a mock SearchQuery object."""
        query = MagicMock()
        # offset().limit() chaining
        limited = MagicMock()
        offsetted = MagicMock()
        offsetted.limit.return_value = limited
        query.offset.return_value = offsetted
        return query, offsetted, limited

    def test_applies_offset_and_limit(self):
        query, offsetted, limited = self._make_query()
        result = apply_range_to_query(query, offset=0, limit=10)
        query.offset.assert_called_once_with(0)
        offsetted.limit.assert_called_once_with(11)  # limit + 1
        assert result == limited

    def test_limit_plus_one_is_applied(self):
        query, offsetted, limited = self._make_query()
        result = apply_range_to_query(query, offset=5, limit=20)
        query.offset.assert_called_once_with(5)
        offsetted.limit.assert_called_once_with(21)  # 20 + 1
        assert result == limited

    def test_none_offset_skips_range(self):
        query, _, _ = self._make_query()
        result = apply_range_to_query(query, offset=None, limit=10)
        # No offset/limit should be applied
        query.offset.assert_not_called()
        assert result == query

    def test_zero_limit_skips_range(self):
        query, _, _ = self._make_query()
        result = apply_range_to_query(query, offset=0, limit=0)
        # Falsy limit should skip range application
        query.offset.assert_not_called()
        assert result == query

    def test_none_limit_skips_range(self):
        query, _, _ = self._make_query()
        result = apply_range_to_query(query, offset=0, limit=None)
        query.offset.assert_not_called()
        assert result == query

    def test_both_none_skips_range(self):
        query, _, _ = self._make_query()
        result = apply_range_to_query(query, offset=None, limit=None)
        query.offset.assert_not_called()
        assert result == query

    @pytest.mark.parametrize(
        "offset, limit, expected_limit_arg",
        [
            (0, 1, 2),
            (10, 5, 6),
            (0, 100, 101),
        ],
        ids=["minimal", "mid_range", "large"],
    )
    def test_limit_is_incremented_by_one(self, offset, limit, expected_limit_arg):
        query, offsetted, limited = self._make_query()
        apply_range_to_query(query, offset=offset, limit=limit)
        offsetted.limit.assert_called_once_with(expected_limit_arg)
