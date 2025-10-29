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

from orchestrator.search.query.results import generate_highlight_indices


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
