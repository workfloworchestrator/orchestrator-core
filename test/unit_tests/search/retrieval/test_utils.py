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

from orchestrator.search.query.results import generate_highlight_indices, truncate_text_with_highlights


class TestGenerateHighlightIndices:
    def test_single_word_match(self):
        text = "The quick brown fox jumps"
        term = "fox"
        result = generate_highlight_indices(text, term)
        assert result == [(16, 19)]

    def test_multiple_word_match(self):
        text = "The quick brown fox jumps over the lazy dog"
        term = "quick fox"
        result = generate_highlight_indices(text, term)
        assert result == [(4, 9), (16, 19)]

    def test_case_insensitive_match(self):
        text = "The QUICK brown FOX jumps"
        term = "quick fox"
        result = generate_highlight_indices(text, term)
        assert result == [(4, 9), (16, 19)]

    def test_substring_fallback(self):
        text = "The quickest brown fox jumps"
        term = "quickest"
        result = generate_highlight_indices(text, term)
        assert result == [(4, 12)]

    def test_empty_inputs(self):
        assert generate_highlight_indices("", "test") == []
        assert generate_highlight_indices("test", "") == []
        assert generate_highlight_indices("", "") == []

    def test_no_matches(self):
        text = "The quick brown fox jumps"
        term = "elephant"
        result = generate_highlight_indices(text, term)
        assert result == []

    def test_duplicate_matches(self):
        text = "fox fox fox"
        term = "fox"
        result = generate_highlight_indices(text, term)
        assert result == [(0, 3), (4, 7), (8, 11)]

    def test_word_and_substring_matches_included(self):
        text = "The Cat sat on the catalog."
        term = "cat"
        result = generate_highlight_indices(text, term)
        assert result == [(4, 7), (19, 22)]


class TestTruncateTextWithHighlights:
    def test_text_shorter_than_max_length(self):
        """Text shorter than max_length should not be truncated."""
        text = "Short text"
        highlights = [(0, 5)]
        result_text, result_highlights = truncate_text_with_highlights(text, highlights, max_length=100)
        assert result_text == "Short text"
        assert result_highlights == [(0, 5)]

    def test_no_highlights_truncates_from_start(self):
        """Text with no highlights should truncate from beginning and add ellipsis."""
        text = "a" * 600
        result_text, result_highlights = truncate_text_with_highlights(text, None, max_length=500)
        assert result_text == ("a" * 500) + "..."
        assert result_highlights is None

    def test_truncate_with_highlight_at_start(self):
        """Highlight at the start should not add leading ellipsis."""
        text = "match" + ("x" * 600)
        highlights = [(0, 5)]
        result_text, result_highlights = truncate_text_with_highlights(text, highlights, max_length=500)
        assert result_text == ("match" + ("x" * 495)) + "..."
        assert result_highlights == [(0, 5)]

    def test_truncate_with_highlight_in_middle(self):
        """Highlight in middle should add ellipsis on both sides."""
        text = ("x" * 300) + "match" + ("y" * 300)
        highlights = [(300, 305)]
        result_text, result_highlights = truncate_text_with_highlights(
            text, highlights, max_length=200, context_chars=50
        )
        # Should center around position 300 with 50 chars context
        # start = max(0, 300 - 50) = 250
        # end = min(605, 250 + 200) = 450
        expected_text = "..." + ("x" * 50) + "match" + ("y" * 145) + "..."
        assert result_text == expected_text
        # Highlight at position 300 becomes position 53 (accounting for leading "...")
        assert result_highlights == [(53, 58)]

    def test_truncate_with_highlight_at_end(self):
        """Highlight near the end should not add trailing ellipsis."""
        text = ("x" * 600) + "match"
        highlights = [(600, 605)]
        result_text, result_highlights = truncate_text_with_highlights(
            text, highlights, max_length=200, context_chars=50
        )
        # Should show context before match
        # First attempt: start = max(0, 600 - 50) = 550, end = min(605, 550 + 200) = 605
        # Since end == len(text), adjust: start = max(0, 605 - 200) = 405
        expected_text = "..." + ("x" * 195) + "match"
        assert result_text == expected_text
        assert result_highlights == [(198, 203)]

    def test_multiple_highlights_uses_first(self):
        """Multiple highlights should center around the first one, excluding highlights outside range."""
        text = ("x" * 100) + "first" + ("y" * 100) + "second" + ("z" * 100)
        highlights = [(100, 105), (205, 211)]
        result_text, result_highlights = truncate_text_with_highlights(
            text, highlights, max_length=150, context_chars=50
        )
        # Should center around first highlight at position 100
        # start = max(0, 100 - 50) = 50
        # end = min(312, 50 + 150) = 200
        expected_text = "..." + ("x" * 50) + "first" + ("y" * 95) + "..."
        assert result_text == expected_text
        # First highlight at 100 becomes 53 (with leading "...")
        # Second highlight at 205 is outside truncated range, so not included
        assert result_highlights == [(53, 58)]

    def test_no_highlights_remain_after_truncation(self):
        """If all highlights are outside truncated range, should return None."""
        text = "x" * 1000
        highlights = [(900, 905)]
        result_text, result_highlights = truncate_text_with_highlights(
            text, highlights, max_length=100, context_chars=10
        )
        # Should center around highlight at 900
        # start = max(0, 900 - 10) = 890
        # end = min(1000, 890 + 100) = 990
        expected_text = "..." + ("x" * 100) + "..."
        assert result_text == expected_text
        assert result_highlights == [(13, 18)]  # Highlight at 900 becomes 13 (890 start + 3 for "...")
