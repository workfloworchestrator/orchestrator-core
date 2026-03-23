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

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from orchestrator.db.models import (
    DESCRIPTION_LENGTH,
    DOMAIN_MODEL_ATTR_LENGTH,
    FAILED_REASON_LENGTH,
    NOTE_LENGTH,
    RESOURCE_VALUE_LENGTH,
    STATUS_LENGTH,
    TAG_LENGTH,
    TRACEBACK_LENGTH,
    StringThatAutoConvertsToNullWhenEmpty,
    UtcTimestamp,
    UtcTimestampError,
)


class TestConstants:
    @pytest.mark.parametrize(
        "constant, expected",
        [
            (TAG_LENGTH, 20),
            (STATUS_LENGTH, 255),
            (NOTE_LENGTH, 5000),
            (DESCRIPTION_LENGTH, 2000),
            (FAILED_REASON_LENGTH, 10000),
            (TRACEBACK_LENGTH, 50000),
            (RESOURCE_VALUE_LENGTH, 10000),
            (DOMAIN_MODEL_ATTR_LENGTH, 255),
        ],
        ids=[
            "TAG_LENGTH",
            "STATUS_LENGTH",
            "NOTE_LENGTH",
            "DESCRIPTION_LENGTH",
            "FAILED_REASON_LENGTH",
            "TRACEBACK_LENGTH",
            "RESOURCE_VALUE_LENGTH",
            "DOMAIN_MODEL_ATTR_LENGTH",
        ],
    )
    def test_constant_value(self, constant: int, expected: int):
        assert constant == expected


class TestUtcTimestampProcessBindParam:
    def setup_method(self):
        self.type_ = UtcTimestamp()
        self.dialect = MagicMock()

    def test_none_returns_none(self):
        assert self.type_.process_bind_param(None, self.dialect) is None

    def test_tz_aware_timestamp_is_returned_unchanged(self):
        ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = self.type_.process_bind_param(ts, self.dialect)
        assert result == ts

    def test_tz_aware_non_utc_is_returned_unchanged(self):
        from datetime import timedelta

        tz_plus2 = timezone(timedelta(hours=2))
        ts = datetime(2024, 6, 1, 14, 0, 0, tzinfo=tz_plus2)
        result = self.type_.process_bind_param(ts, self.dialect)
        assert result == ts

    def test_naive_timestamp_raises_utc_timestamp_error(self):
        naive_ts = datetime(2024, 1, 15, 12, 0, 0)
        with pytest.raises(UtcTimestampError):
            self.type_.process_bind_param(naive_ts, self.dialect)

    def test_naive_timestamp_error_message_contains_value(self):
        naive_ts = datetime(2024, 1, 15, 12, 0, 0)
        with pytest.raises(UtcTimestampError, match="naive timestamp"):
            self.type_.process_bind_param(naive_ts, self.dialect)

    def test_utc_timestamp_error_is_exception(self):
        assert issubclass(UtcTimestampError, Exception)


class TestUtcTimestampProcessResultValue:
    def setup_method(self):
        self.type_ = UtcTimestamp()
        self.dialect = MagicMock()

    def test_none_returns_none(self):
        assert self.type_.process_result_value(None, self.dialect) is None

    def test_utc_timestamp_remains_utc(self):
        ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = self.type_.process_result_value(ts, self.dialect)
        assert result.tzinfo == timezone.utc

    def test_non_utc_timestamp_is_converted_to_utc(self):
        from datetime import timedelta

        tz_plus2 = timezone(timedelta(hours=2))
        ts = datetime(2024, 6, 1, 14, 0, 0, tzinfo=tz_plus2)
        result = self.type_.process_result_value(ts, self.dialect)
        assert result.tzinfo == timezone.utc
        # 14:00 +02:00 == 12:00 UTC
        assert result.hour == 12

    def test_result_preserves_point_in_time(self):
        from datetime import timedelta

        tz_minus5 = timezone(timedelta(hours=-5))
        ts = datetime(2024, 3, 10, 8, 30, 0, tzinfo=tz_minus5)
        result = self.type_.process_result_value(ts, self.dialect)
        # 08:30 -05:00 == 13:30 UTC
        assert result == datetime(2024, 3, 10, 13, 30, 0, tzinfo=timezone.utc)

    @pytest.mark.parametrize(
        "falsy_value",
        [None, 0, False, ""],
        ids=["none", "zero", "false", "empty_string"],
    )
    def test_falsy_value_returns_value_unchanged(self, falsy_value):
        result = self.type_.process_result_value(falsy_value, self.dialect)
        assert result == falsy_value


class TestStringThatAutoConvertsToNullWhenEmptyProcessBindParam:
    def setup_method(self):
        self.type_ = StringThatAutoConvertsToNullWhenEmpty()
        self.dialect = MagicMock()

    def test_none_returns_none(self):
        assert self.type_.process_bind_param(None, self.dialect) is None

    def test_empty_string_returns_none(self):
        assert self.type_.process_bind_param("", self.dialect) is None

    def test_whitespace_only_returns_none(self):
        assert self.type_.process_bind_param("   ", self.dialect) is None

    def test_tab_only_returns_none(self):
        assert self.type_.process_bind_param("\t", self.dialect) is None

    def test_newline_only_returns_none(self):
        assert self.type_.process_bind_param("\n", self.dialect) is None

    def test_mixed_whitespace_returns_none(self):
        assert self.type_.process_bind_param("  \t\n  ", self.dialect) is None

    def test_normal_string_is_returned_unchanged(self):
        assert self.type_.process_bind_param("hello", self.dialect) == "hello"

    def test_string_with_leading_whitespace_is_returned_unchanged(self):
        assert self.type_.process_bind_param("  hello", self.dialect) == "  hello"

    def test_string_with_trailing_whitespace_is_returned_unchanged(self):
        assert self.type_.process_bind_param("hello  ", self.dialect) == "hello  "

    def test_string_with_surrounding_whitespace_is_returned_unchanged(self):
        assert self.type_.process_bind_param("  hello  ", self.dialect) == "  hello  "

    def test_zero_as_string_is_returned_unchanged(self):
        assert self.type_.process_bind_param("0", self.dialect) == "0"

    def test_false_as_string_is_returned_unchanged(self):
        assert self.type_.process_bind_param("false", self.dialect) == "false"

    @pytest.mark.parametrize(
        "value, expected",
        [
            (None, None),
            ("", None),
            ("   ", None),
            ("hello", "hello"),
            ("  world  ", "  world  "),
            ("0", "0"),
        ],
        ids=["none", "empty", "whitespace", "word", "padded_word", "zero_string"],
    )
    def test_parametrized_bind_param(self, value, expected):
        assert self.type_.process_bind_param(value, self.dialect) == expected


class TestStringThatAutoConvertsToNullWhenEmptyProcessResultValue:
    def setup_method(self):
        self.type_ = StringThatAutoConvertsToNullWhenEmpty()
        self.dialect = MagicMock()

    def test_none_returns_none(self):
        assert self.type_.process_result_value(None, self.dialect) is None

    def test_string_is_returned_unchanged(self):
        assert self.type_.process_result_value("hello", self.dialect) == "hello"

    def test_empty_string_is_returned_unchanged(self):
        # process_result_value does NOT convert — only process_bind_param does
        assert self.type_.process_result_value("", self.dialect) == ""

    def test_whitespace_is_returned_unchanged(self):
        assert self.type_.process_result_value("   ", self.dialect) == "   "

    @pytest.mark.parametrize(
        "value",
        [None, "", "   ", "hello", "  world  "],
        ids=["none", "empty", "whitespace", "word", "padded_word"],
    )
    def test_result_value_always_passes_through(self, value):
        assert self.type_.process_result_value(value, self.dialect) == value


class TestStringThatAutoConvertsToNullWhenEmptyMeta:
    def test_cache_ok_is_true(self):
        assert StringThatAutoConvertsToNullWhenEmpty.cache_ok is True

    def test_python_type_is_str(self):
        assert StringThatAutoConvertsToNullWhenEmpty.python_type is str

    def test_accepts_optional_length(self):
        t = StringThatAutoConvertsToNullWhenEmpty(length=255)
        assert t is not None

    def test_accepts_no_length(self):
        t = StringThatAutoConvertsToNullWhenEmpty()
        assert t is not None


class TestUtcTimestampMeta:
    def test_cache_ok_is_false(self):
        assert UtcTimestamp.cache_ok is False

    def test_python_type_is_datetime(self):
        assert UtcTimestamp.python_type is datetime
