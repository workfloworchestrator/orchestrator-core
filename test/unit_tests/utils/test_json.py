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

import ipaddress
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import numpy as np
import pytest
import pytz
from pydantic import BaseModel

from orchestrator.core.schemas.base import OrchestratorBaseModel
from orchestrator.core.utils.datetime import nowtz
from orchestrator.core.utils.json import from_serializable, json_dumps, json_loads, non_none_dict, to_serializable


def test_serialization_datetime():
    json_str = json_dumps({"end_date": nowtz()})
    assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", json_str)


def test_deserialization_datetime():
    json_str = '{"end_date": "2019-12-06T19:25:22+00:00"}'
    dct = json_loads(json_str)
    assert "end_date" in dct
    assert dct["end_date"] == datetime(2019, 12, 6, 19, 25, 22, 0, timezone.utc)

    dct = {"end_date": datetime(2019, 12, 6, 19, 25, 22, 0, timezone.utc)}
    assert json_loads(json_dumps(dct)) == dct


def test_no_none_dict():
    assert non_none_dict({}.items()) == {}
    assert non_none_dict({"a": 0, "b": None, "c": ""}.items()) == {"a": 0, "c": ""}


def test_to_serializable():
    assert to_serializable(UUID("3ec5fad4-e58c-4cb3-a860-6764cfc658f3")) == "3ec5fad4-e58c-4cb3-a860-6764cfc658f3"
    assert to_serializable(ipaddress.ip_address("10.0.0.1")) == "10.0.0.1"
    assert to_serializable(ipaddress.ip_address("fd00::1")) == "fd00::1"
    assert to_serializable(ipaddress.ip_network("10.0.0.0/24")) == "10.0.0.0/24"
    assert to_serializable(ipaddress.ip_network("fd00::0/64")) == "fd00::/64"
    assert to_serializable(datetime(2021, 7, 28, 1, 1, 1)) == "2021-07-28T01:01:01"
    assert to_serializable({3, 4, 5, 5, 6}) == [3, 4, 5, 6]

    @dataclass
    class Foo:
        bar: int

    assert to_serializable(Foo(1)) == {"bar": 1}

    class Foo:
        def __json__(self):
            return {"bar": 1}

    assert to_serializable(Foo()) == {"bar": 1}

    class Foo:
        def to_dict(self):
            return {"bar": 1}

    assert to_serializable(Foo()) == {"bar": 1}

    class Foo(BaseModel):
        bar: int

    assert to_serializable(Foo(bar=1)) == {"bar": 1}

    with pytest.raises(TypeError, match=r"Could not serialize object of type int to JSON"):
        to_serializable(1)


def test_from_serializable():
    assert from_serializable(
        {"date": "2021-07-28T01:01:01+00:00", "date-to-short": "2021-07-28T01:01:01", "int": 1}
    ) == {
        "date": datetime(2021, 7, 28, 1, 1, 1, tzinfo=pytz.UTC),
        "date-to-short": "2021-07-28T01:01:01",
        "int": 1,
    }


def test_orchestrator_base_serializer():

    class Foo(OrchestratorBaseModel):
        baz: datetime
        bar: int

    foo = Foo(baz=datetime(2024, 12, 1, 1, 1), bar=1)
    assert foo.model_dump(mode="json") == {"baz": datetime(2024, 12, 1, 1, 1).timestamp(), "bar": 1}


def test_orchestrator_base_serializer_recursive():
    class Bar(OrchestratorBaseModel):
        baz: datetime

    class Foo(OrchestratorBaseModel):
        baz: datetime
        nested_bar: Bar
        bing: int

    foo = Foo(baz=datetime(2024, 12, 1, 1, 1), nested_bar=Bar(baz=datetime(2024, 11, 1, 1, 1)), bing=1)
    assert foo.model_dump(mode="json") == {
        "baz": datetime(2024, 12, 1, 1, 1).timestamp(),
        "nested_bar": {"baz": datetime(2024, 11, 1, 1, 1).timestamp()},
        "bing": 1,
    }


@pytest.mark.parametrize("value,expected", [
    (np.int64(42), 42),
    (np.int32(7), 7),
])
def test_numpy_integer_to_int(value, expected):
    result = to_serializable(value)
    assert result == expected
    assert type(result) is int


@pytest.mark.parametrize("value,expected", [
    (np.float64(3.14), 3.14),
    (np.float32(2.5), pytest.approx(2.5, rel=1e-5)),
])
def test_numpy_floating_to_float(value, expected):
    result = to_serializable(value)
    assert result == expected
    assert type(result) is float


@pytest.mark.parametrize("value,expected", [
    (np.bool_(True), True),
    (np.bool_(False), False),
])
def test_numpy_bool_to_bool(value, expected):
    result = to_serializable(value)
    assert result == expected
    assert type(result) is bool


def test_numpy_ndarray_to_list():
    arr = np.array([1, 2, 3])
    result = to_serializable(arr)
    assert result == [1, 2, 3]
    assert type(result) is list


def test_numpy_round_trip_json_dumps():
    data = {"count": np.int64(42), "values": np.array([1.0, 2.0])}
    json_str = json_dumps(data)
    parsed = json.loads(json_str)
    assert parsed["count"] == 42
    assert type(parsed["count"]) is int
    assert parsed["values"] == [1.0, 2.0]
    assert type(parsed["values"]) is list
