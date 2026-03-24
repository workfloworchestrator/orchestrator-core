"""Tests for search retrieval utils: highlight index generation and text truncation with highlights."""

# Copyright 2019-2025 SURF, GÉANT.
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

import pytest

from orchestrator.search.query.results import generate_highlight_indices, truncate_text_with_highlights


@pytest.mark.parametrize(
    "text,term,expected",
    [
        pytest.param("The quick brown fox jumps", "fox", [(16, 19)], id="single-word"),
        pytest.param(
            "The quick brown fox jumps over the lazy dog", "quick fox", [(4, 9), (16, 19)], id="multiple-words"
        ),
        pytest.param("The QUICK brown FOX jumps", "quick fox", [(4, 9), (16, 19)], id="case-insensitive"),
        pytest.param("The quickest brown fox jumps", "quickest", [(4, 12)], id="substring"),
        pytest.param("The quick brown fox jumps", "elephant", [], id="no-match"),
        pytest.param("fox fox fox", "fox", [(0, 3), (4, 7), (8, 11)], id="duplicate-matches"),
        pytest.param("The Cat sat on the catalog.", "cat", [(4, 7), (19, 22)], id="word-and-substring"),
    ],
)
def test_generate_highlight_indices(text: str, term: str, expected: list):
    assert generate_highlight_indices(text, term) == expected


@pytest.mark.parametrize(
    "text,term",
    [
        pytest.param("", "test", id="empty-text"),
        pytest.param("test", "", id="empty-term"),
        pytest.param("", "", id="both-empty"),
    ],
)
def test_generate_highlight_indices_empty_inputs(text: str, term: str):
    assert generate_highlight_indices(text, term) == []


def test_truncate_text_shorter_than_max():
    text = "Short text"
    highlights = [(0, 5)]
    result_text, result_highlights = truncate_text_with_highlights(text, highlights, max_length=100)
    assert result_text == "Short text"
    assert result_highlights == [(0, 5)]


def test_truncate_no_highlights():
    text = "a" * 600
    result_text, result_highlights = truncate_text_with_highlights(text, None, max_length=500)
    assert result_text == ("a" * 500) + "..."
    assert result_highlights is None


def test_truncate_highlight_at_start():
    text = "match" + ("x" * 600)
    highlights = [(0, 5)]
    result_text, result_highlights = truncate_text_with_highlights(text, highlights, max_length=500)
    assert result_text == ("match" + ("x" * 495)) + "..."
    assert result_highlights == [(0, 5)]


def test_truncate_highlight_in_middle():
    text = ("x" * 300) + "match" + ("y" * 300)
    highlights = [(300, 305)]
    result_text, result_highlights = truncate_text_with_highlights(text, highlights, max_length=200, context_chars=50)
    expected_text = "..." + ("x" * 50) + "match" + ("y" * 145) + "..."
    assert result_text == expected_text
    assert result_highlights == [(53, 58)]


def test_truncate_highlight_at_end():
    text = ("x" * 600) + "match"
    highlights = [(600, 605)]
    result_text, result_highlights = truncate_text_with_highlights(text, highlights, max_length=200, context_chars=50)
    expected_text = "..." + ("x" * 195) + "match"
    assert result_text == expected_text
    assert result_highlights == [(198, 203)]


_MULTI_HIGHLIGHTS = [(100, 105), (205, 211)]


def test_truncate_multiple_highlights_uses_first():
    text = ("x" * 100) + "first" + ("y" * 100) + "second" + ("z" * 100)
    highlights = _MULTI_HIGHLIGHTS
    result_text, result_highlights = truncate_text_with_highlights(text, highlights, max_length=150, context_chars=50)
    expected_text = "..." + ("x" * 50) + "first" + ("y" * 95) + "..."
    assert result_text == expected_text
    assert result_highlights == [(53, 58)]


def test_truncate_highlights_centered_on_far_highlight():
    text = "x" * 1000
    highlights = [(900, 905)]
    result_text, result_highlights = truncate_text_with_highlights(text, highlights, max_length=100, context_chars=10)
    expected_text = "..." + ("x" * 100) + "..."
    assert result_text == expected_text
    assert result_highlights == [(13, 18)]
