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

"""Tests for custom SQLAlchemy TypeDecorators: UtcTimestamp (timezone enforcement) and StringThatAutoConvertsToNullWhenEmpty."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from orchestrator.core.db.models import (
    StringThatAutoConvertsToNullWhenEmpty,
    UtcTimestamp,
    UtcTimestampError,
)

_UTC_TS = UtcTimestamp()
_STR_NULL = StringThatAutoConvertsToNullWhenEmpty()
_DIALECT = MagicMock()


# --- UtcTimestamp.process_bind_param ---


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param(None, None, id="none"),
        pytest.param(
            datetime(2024, 1, 15, 12, tzinfo=timezone.utc), datetime(2024, 1, 15, 12, tzinfo=timezone.utc), id="utc"
        ),
        pytest.param(
            datetime(2024, 6, 1, 14, tzinfo=timezone(timedelta(hours=2))),
            datetime(2024, 6, 1, 14, tzinfo=timezone(timedelta(hours=2))),
            id="non-utc-passthrough",
        ),
    ],
)
def test_utc_timestamp_bind_param_valid(value: datetime | None, expected: datetime | None) -> None:
    assert _UTC_TS.process_bind_param(value, _DIALECT) == expected


def test_utc_timestamp_bind_param_naive_raises() -> None:
    with pytest.raises(UtcTimestampError, match="naive timestamp"):
        _UTC_TS.process_bind_param(datetime(2024, 1, 15, 12), _DIALECT)


# --- UtcTimestamp.process_result_value ---


@pytest.mark.parametrize(
    "value,expected_hour",
    [
        pytest.param(None, None, id="none"),
        pytest.param(datetime(2024, 1, 15, 12, tzinfo=timezone.utc), 12, id="utc-unchanged"),
        pytest.param(datetime(2024, 6, 1, 14, tzinfo=timezone(timedelta(hours=2))), 12, id="plus2-to-utc"),
        pytest.param(datetime(2024, 3, 10, 8, 30, tzinfo=timezone(timedelta(hours=-5))), 13, id="minus5-to-utc"),
    ],
)
def test_utc_timestamp_result_value(value: datetime | None, expected_hour: int | None) -> None:
    result = _UTC_TS.process_result_value(value, _DIALECT)
    if expected_hour is None:
        assert result is None
    else:
        assert result is not None
        assert result.tzinfo == timezone.utc
        assert result.hour == expected_hour


# --- StringThatAutoConvertsToNullWhenEmpty.process_bind_param ---


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param(None, None, id="none"),
        pytest.param("", None, id="empty"),
        pytest.param("   ", None, id="spaces"),
        pytest.param("\t", None, id="tab"),
        pytest.param("\n", None, id="newline"),
        pytest.param("  \t\n  ", None, id="mixed-whitespace"),
        pytest.param("hello", "hello", id="normal"),
        pytest.param("  hello  ", "  hello  ", id="padded"),
        pytest.param("0", "0", id="zero-string"),
    ],
)
def test_string_null_bind_param(value: str | None, expected: str | None) -> None:
    assert _STR_NULL.process_bind_param(value, _DIALECT) == expected


# --- StringThatAutoConvertsToNullWhenEmpty.process_result_value ---


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="none"),
        pytest.param("", id="empty"),
        pytest.param("   ", id="whitespace"),
        pytest.param("hello", id="word"),
    ],
)
def test_string_null_result_value_passthrough(value: str | None) -> None:
    assert _STR_NULL.process_result_value(value, _DIALECT) == value
