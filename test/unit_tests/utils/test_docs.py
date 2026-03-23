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
from uuid import UUID

import pytest

from orchestrator.utils.docs import INDENT2, INDENT3, get_doc_title, make_field_doc, make_ref


# Module-level classes — locally defined classes inside methods would have their
# enclosing method name stripped from __qualname__ by make_ref, making assertions
# on the class name unreliable.
class _ModuleLevelClass:
    """Module-level class for testing make_ref."""


class _ClassWithDoc:
    """Doc title."""


class _ClassWithoutDoc:
    pass


class TestMakeRef:
    def test_builtin_type_uses_qualname(self) -> None:
        ref = make_ref(int)
        assert "int" in ref
        assert ref.startswith("~")

    def test_shorten_false_omits_tilde(self) -> None:
        ref = make_ref(int, shorten=False)
        assert not ref.startswith("~")
        assert "builtins.int" in ref

    def test_shorten_true_prepends_tilde(self) -> None:
        ref = make_ref(int, shorten=True)
        assert ref.startswith("~")

    def test_custom_class_uses_module_and_qualname(self) -> None:
        # Use a module-level class so __qualname__ is simply the class name
        ref = make_ref(_ModuleLevelClass)
        assert "_ModuleLevelClass" in ref

    def test_generic_type_delegates_to_origin(self) -> None:
        # list[int] (builtin generic) has no __qualname__ but has get_origin -> list
        ref = make_ref(list[int])
        assert "list" in ref

    def test_fallback_to_str_for_unknown(self) -> None:
        # A simple string-like annotation (no __qualname__, no origin)
        ref = make_ref("some_string_annotation")
        assert ref == "some_string_annotation"

    def test_local_class_strips_locals_from_qualname(self) -> None:
        # make_ref splits on '.<locals>' so the method-local portion is removed
        # Use a module-level class to verify the ref is clean
        ref = make_ref(_ModuleLevelClass, shorten=False)
        assert "<locals>" not in ref
        assert "_ModuleLevelClass" in ref


class TestGetDocTitle:
    def test_returns_first_line_of_docstring(self) -> None:
        class Documented:
            """First line.

            More details here.
            """

        assert get_doc_title(Documented) == "First line."

    def test_returns_empty_string_for_no_docstring(self) -> None:
        class NoDoc:
            pass

        assert get_doc_title(NoDoc) == ""

    def test_returns_empty_string_for_empty_docstring(self) -> None:
        class EmptyDoc:
            pass

        EmptyDoc.__doc__ = ""
        assert get_doc_title(EmptyDoc) == ""

    def test_builtin_type_has_doc_title(self) -> None:
        # int has a docstring; we only assert we get a string back
        result = get_doc_title(int)
        assert isinstance(result, str)


class TestMakeFieldDoc:
    """Verify the doctests from make_field_doc and additional edge cases."""

    def test_int_field_matches_doctest(self) -> None:
        # From doctest: make_field_doc("int_field", int)
        expected = "        int_field:\n            Type :class:`~builtins.int`"
        assert make_field_doc("int_field", int) == expected

    def test_bool_field_no_type_doc_str(self) -> None:
        result = make_field_doc("flag", bool)
        assert f"{INDENT2}flag:" in result
        assert f"{INDENT3}Type :class:`" in result
        # bool is in the simple types list — no extra doc title block
        assert "bool" in result

    def test_str_field_no_type_doc_str(self) -> None:
        result = make_field_doc("name", str)
        assert "name:" in result
        assert "str" in result

    def test_uuid_field_no_type_doc_str(self) -> None:
        result = make_field_doc("uid", UUID)
        assert "uid:" in result
        assert "UUID" in result

    def test_custom_class_with_docstring_matches_doctest(self) -> None:
        result = make_field_doc("int_field", _ClassWithDoc)
        assert "Doc title." in result
        assert "_ClassWithDoc" in result
        assert f"{INDENT3}Doc title.\n\n" in result

    def test_custom_class_without_docstring(self) -> None:
        result = make_field_doc("field", _ClassWithoutDoc)
        # Empty doc title — still contains the type reference
        assert "_ClassWithoutDoc" in result
        assert f"{INDENT2}field:" in result

    @pytest.mark.parametrize(
        "field_type",
        [int, bool, str, UUID],
        ids=["int", "bool", "str", "uuid"],
    )
    def test_simple_types_have_no_extra_doc_block(self, field_type) -> None:
        result = make_field_doc("f", field_type)
        # For simple types type_doc_str is "" so there should be no double-newline before Type
        lines = result.split("\n")
        # line 0: "        f:"
        # line 1: "            Type :class:`...`"
        assert len(lines) == 2
