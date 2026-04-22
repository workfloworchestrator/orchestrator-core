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

"""Tests for doc generation utilities: make_ref (type cross-references), get_doc_title, and make_field_doc."""

from uuid import UUID

import pytest

from orchestrator.core.utils.docs import INDENT3, get_doc_title, make_field_doc, make_ref


class _ClassWithDoc:
    """Doc title."""


class _ClassWithoutDoc:
    pass


# --- make_ref ---


@pytest.mark.parametrize(
    "shorten,expected_prefix",
    [
        pytest.param(True, "~", id="shortened"),
        pytest.param(False, "", id="full"),
    ],
)
def test_make_ref_shorten_flag(shorten: bool, expected_prefix: str) -> None:
    ref = make_ref(int, shorten=shorten)
    assert ref.startswith(expected_prefix)
    assert "int" in ref


def test_make_ref_generic_type() -> None:
    ref = make_ref(list[int])
    assert "list" in ref


def test_make_ref_fallback_to_str() -> None:
    assert make_ref("some_string_annotation") == "some_string_annotation"


# --- get_doc_title ---


def test_get_doc_title_returns_first_line() -> None:
    class Documented:
        """First line.

        More details.
        """

    assert get_doc_title(Documented) == "First line."


@pytest.mark.parametrize(
    "cls",
    [
        pytest.param(_ClassWithoutDoc, id="no-doc"),
    ],
)
def test_get_doc_title_returns_empty_for_undocumented(cls: type) -> None:
    assert get_doc_title(cls) == ""


# --- make_field_doc ---


def test_make_field_doc_int_matches_doctest() -> None:
    expected = "        int_field:\n            Type :class:`~builtins.int`"
    assert make_field_doc("int_field", int) == expected


def test_make_field_doc_custom_class_includes_doc_title() -> None:
    result = make_field_doc("field", _ClassWithDoc)
    assert "Doc title." in result
    assert f"{INDENT3}Doc title.\n\n" in result


@pytest.mark.parametrize(
    "field_type",
    [
        pytest.param(int, id="int"),
        pytest.param(bool, id="bool"),
        pytest.param(str, id="str"),
        pytest.param(UUID, id="uuid"),
    ],
)
def test_simple_types_produce_two_line_output(field_type: type) -> None:
    result = make_field_doc("f", field_type)
    assert len(result.split("\n")) == 2
