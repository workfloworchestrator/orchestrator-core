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

"""``walk_form``: ``post_form``'s walk, ending in the next page, the result, or the rejected page."""

import pytest

from orchestrator.core.forms import FormPage, post_form
from orchestrator.core.forms.walk import Complete, NextPage, Rejected, walk_form
from pydantic_forms.exceptions import FormOverflowError, FormValidationError


class First(FormPage):
    name: str


class Second(FormPage):
    count: int = 1


def two_pages(state):
    first = yield First
    second = yield Second
    return {**state, **first.model_dump(), **second.model_dump()}


def test_the_walk_ends_at_the_next_page_or_at_the_result_post_form_gives():
    assert walk_form(two_pages, {}, []) == NextPage(First, 0)
    assert walk_form(two_pages, {}, [{"name": "a"}]) == NextPage(Second, 1)
    done = [{"name": "a"}, {"count": 2}]
    assert walk_form(two_pages, {"reporter": "r"}, done) == Complete(post_form(two_pages, {"reporter": "r"}, done))
    assert walk_form(None, {"reporter": "r"}, []) == Complete({})


def test_a_rejected_page_is_named_with_the_verdict_post_form_raises():
    bad = [{"name": "a"}, {"count": "many"}]
    with pytest.raises(FormValidationError) as raised:
        post_form(two_pages, {}, bad)
    rejected = walk_form(two_pages, {}, bad)
    assert isinstance(rejected, Rejected)
    assert (rejected.model, rejected.index) == (Second, 1)
    assert rejected.error.errors == raised.value.errors  # the same verdict, translated the same way
    assert [(e["loc"], e["type"]) for e in rejected.error.errors] == [(("count",), "int_parsing")]


def test_more_inputs_than_pages_overflow():
    with pytest.raises(FormOverflowError):
        walk_form(two_pages, {}, [{"name": "a"}, {"count": 2}, {}])
