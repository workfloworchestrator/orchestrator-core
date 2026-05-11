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

import warnings

import pytest

from orchestrator.core.api.helpers import (
    add_subscription_search_query_filter,
    get_in,
    getattr_in,
    update_in,
)


class BasicObject:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


SAMPLE_OBJECT = BasicObject(foo=BasicObject(bar="a", baz=[BasicObject(fooo=123)]))


@pytest.mark.parametrize(
    "input_object,path,expected_result",
    [
        ({"foo": "bar"}, "fizz", None),
        ({"foo": "bar"}, "foo", "bar"),
        ({"foo": {"bar": {"fizz": "buzz"}}}, "foo.bar.fizz", "buzz"),
        ({"foo": {"barbar": {"fizz": "buzz"}}}, "foo.bar.fizz", None),
        ({"foo": {"bar": {"fizz": ["a", "b", "c"]}}}, "foo.bar.fizz.1", "b"),
        ({"foo": {"bar": {"fizz": ["a", "b", "c"]}}}, "foo.bar.fizz.4", IndexError),
        ({"foo": {"bar": {"fizz": ["a", "b", "c"]}}}, "foo.bar", {"fizz": ["a", "b", "c"]}),
        (BasicObject(), "foo.bar", None),
        (SAMPLE_OBJECT, "foo.bar", "a"),
        (SAMPLE_OBJECT, "foo.barbar", None),
        (SAMPLE_OBJECT, "foo.baz.0.fooo", 123),
        (SAMPLE_OBJECT, "foo.baz.10.fooo", IndexError),
    ],
)
def test_getattr_in(input_object, path, expected_result):
    if isinstance(expected_result, type) and issubclass(expected_result, Exception):
        with pytest.raises(expected_result):
            getattr_in(input_object, path)
    else:
        assert getattr_in(input_object, path) == expected_result


@pytest.mark.parametrize(
    "input_dict,path,value,expected_result",
    [
        pytest.param({}, "foo", "bar", {"foo": "bar"}),
        pytest.param(
            {},
            "foo.x",
            "bar",
            {"foo": {"x": "bar"}},
            marks=[pytest.mark.xfail(reason="Intermediate dicts not created")],
        ),
        pytest.param({"foo": {}}, "foo.x", "bar", {"foo": {"x": "bar"}}),
        pytest.param(
            {},
            "foo.x.y",
            "bar",
            {"foo": {"x": {"y": "bar"}}},
            marks=[pytest.mark.xfail(reason="Intermediate dicts not created")],
        ),
        pytest.param({"foo": "bar"}, "fizz", "buzz", {"foo": "bar", "fizz": "buzz"}),
        pytest.param(
            {"foo": ["bar"]}, "foo.0", "buzz", {"foo": ["buzz"]}, marks=[pytest.mark.xfail(reason="Raises TypeError")]
        ),
    ],
)
def test_update_in(input_dict, path, value, expected_result):
    # TODO fix the failing scenarios
    assert update_in(input_dict, path, value) is None
    assert input_dict == expected_result


@pytest.mark.parametrize(
    "dct,path,expected",
    [
        # simple key lookup
        ({"a": 1}, "a", 1),
        # nested dict path
        ({"a": {"b": {"c": 42}}}, "a.b.c", 42),
        # nested: dict then list then dict (list in the middle, final lookup is dict key)
        ({"a": [{"b": 99}]}, "a.0.b", 99),
    ],
)
def test_get_in(dct, path, expected):
    assert get_in(dct, path) == expected


def test_get_in_list_as_final_segment_raises_type_error():
    # get_in uses prev[x] with string x at the end, which fails on list
    with pytest.raises(TypeError):
        get_in({"a": [10, 20, 30]}, "a.1")


def test_get_in_missing_key_raises():
    # dict.get(x) returns None, then prev[x] does a real key lookup and raises
    with pytest.raises(KeyError):
        get_in({"a": 1}, "b")


def test_get_in_missing_nested_key_raises():
    # dict.get("c") returns None, then prev["c"] raises KeyError
    with pytest.raises(KeyError):
        get_in({"a": {"b": 1}}, "a.c")


def test_get_in_list_index_out_of_range():
    with pytest.raises(IndexError):
        get_in({"a": [1, 2, 3]}, "a.10")


def test_subscription_search_query_filter_emits_deprecation_warning():
    """TSV search should emit a deprecation warning pointing to LLM search."""
    from sqlalchemy import select

    from orchestrator.core.db import SubscriptionTable

    stmt = select(SubscriptionTable)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        add_subscription_search_query_filter(stmt, "test")
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) == 1
        assert "deprecated" in str(deprecation_warnings[0].message).lower()
        assert "/api/search" in str(deprecation_warnings[0].message)
