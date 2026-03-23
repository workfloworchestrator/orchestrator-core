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

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import litellm.exceptions as llm_exc
import pytest

from orchestrator.search.core.embedding import EmbeddingIndexer, QueryEmbedder

pytestmark = pytest.mark.search

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_SETTINGS = {
    "EMBEDDING_MODEL": "openai/text-embedding-3-small",
    "OPENAI_API_KEY": "test-key",
    "OPENAI_BASE_URL": None,
    "LLM_TIMEOUT": 30,
    "LLM_MAX_RETRIES": 3,
    "EMBEDDING_DIMENSION": 3,
}


def _make_settings_mock() -> MagicMock:
    mock = MagicMock()
    for attr, val in _FAKE_SETTINGS.items():
        setattr(mock, attr, val)
    return mock


def _make_embedding_response(embeddings: list[list[float]]) -> MagicMock:
    """Build a fake litellm embedding response with proper index ordering."""
    resp = MagicMock()
    resp.data = [{"index": i, "embedding": emb} for i, emb in enumerate(embeddings)]
    return resp


# ---------------------------------------------------------------------------
# EmbeddingIndexer
# ---------------------------------------------------------------------------


class TestEmbeddingIndexerEmptyTexts:
    def test_empty_list_returns_empty(self):
        result = EmbeddingIndexer.get_embeddings_from_api_batch([], dry_run=False)
        assert result == []

    def test_empty_list_dry_run_returns_empty(self):
        result = EmbeddingIndexer.get_embeddings_from_api_batch([], dry_run=True)
        assert result == []


class TestEmbeddingIndexerDryRun:
    @pytest.mark.parametrize(
        "texts",
        [
            ["hello"],
            ["hello", "world"],
            ["a", "b", "c", "d"],
        ],
    )
    def test_dry_run_returns_empty_list_per_text(self, texts):
        result = EmbeddingIndexer.get_embeddings_from_api_batch(texts, dry_run=True)
        assert result == [[] for _ in texts]


class TestEmbeddingIndexerSuccess:
    def test_successful_batch_returns_truncated_embeddings(self):
        settings_mock = _make_settings_mock()
        # Return embeddings longer than EMBEDDING_DIMENSION (3) to verify truncation
        raw_embeddings = [[0.1, 0.2, 0.3, 0.4, 0.5], [0.6, 0.7, 0.8, 0.9, 1.0]]
        resp_mock = _make_embedding_response(raw_embeddings)

        with (
            patch("orchestrator.search.core.embedding.llm_embedding", return_value=resp_mock),
            patch("orchestrator.search.core.embedding.llm_settings", settings_mock),
        ):
            result = EmbeddingIndexer.get_embeddings_from_api_batch(["hello", "world"], dry_run=False)

        assert result == [[0.1, 0.2, 0.3], [0.6, 0.7, 0.8]]

    def test_successful_batch_sorts_by_index(self):
        """Response data returned out of order must be sorted by index before returning."""
        settings_mock = _make_settings_mock()
        resp = MagicMock()
        # Reversed index order
        resp.data = [
            {"index": 1, "embedding": [0.9, 0.8, 0.7, 0.6]},
            {"index": 0, "embedding": [0.1, 0.2, 0.3, 0.4]},
        ]

        with (
            patch("orchestrator.search.core.embedding.llm_embedding", return_value=resp),
            patch("orchestrator.search.core.embedding.llm_settings", settings_mock),
        ):
            result = EmbeddingIndexer.get_embeddings_from_api_batch(["first", "second"], dry_run=False)

        # After sorting by index: [index=0, index=1], then truncated to dim=3
        assert result == [[0.1, 0.2, 0.3], [0.9, 0.8, 0.7]]

    def test_inputs_are_lowercased_before_api_call(self):
        settings_mock = _make_settings_mock()
        resp_mock = _make_embedding_response([[0.1, 0.2, 0.3]])

        with (
            patch("orchestrator.search.core.embedding.llm_embedding", return_value=resp_mock) as mock_embed,
            patch("orchestrator.search.core.embedding.llm_settings", settings_mock),
        ):
            EmbeddingIndexer.get_embeddings_from_api_batch(["HELLO"], dry_run=False)

        call_kwargs = mock_embed.call_args.kwargs
        assert call_kwargs["input"] == ["hello"]


class TestEmbeddingIndexerAPIErrors:
    @pytest.mark.parametrize(
        "exception",
        [
            llm_exc.APIError(500, "server error", "openai", "test-model", request=httpx.Request("GET", "http://x")),
            llm_exc.APIConnectionError("connection failed", "openai", "test-model"),
            llm_exc.RateLimitError("rate limited", llm_provider="openai", model="test-model"),
            llm_exc.Timeout("timed out", model="test-model", llm_provider="openai"),
        ],
    )
    def test_known_api_errors_return_empty_embeddings(self, exception):
        settings_mock = _make_settings_mock()
        texts = ["hello", "world"]

        with (
            patch("orchestrator.search.core.embedding.llm_embedding", side_effect=exception),
            patch("orchestrator.search.core.embedding.llm_settings", settings_mock),
        ):
            result = EmbeddingIndexer.get_embeddings_from_api_batch(texts, dry_run=False)

        assert result == [[], []]

    def test_unexpected_error_returns_empty_embeddings(self):
        settings_mock = _make_settings_mock()
        texts = ["a", "b", "c"]

        with (
            patch("orchestrator.search.core.embedding.llm_embedding", side_effect=RuntimeError("boom")),
            patch("orchestrator.search.core.embedding.llm_settings", settings_mock),
        ):
            result = EmbeddingIndexer.get_embeddings_from_api_batch(texts, dry_run=False)

        assert result == [[], [], []]


# ---------------------------------------------------------------------------
# QueryEmbedder
# ---------------------------------------------------------------------------


class TestQueryEmbedderEmptyText:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("text", ["", None])
    async def test_empty_or_none_returns_empty(self, text):
        result = await QueryEmbedder.generate_for_text_async(text)
        assert result == []


class TestQueryEmbedderSuccess:
    @pytest.mark.asyncio
    async def test_returns_truncated_embedding(self):
        settings_mock = _make_settings_mock()
        raw_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        resp_mock = MagicMock()
        resp_mock.data = [{"embedding": raw_embedding}]

        with (
            patch("orchestrator.search.core.embedding.llm_aembedding", new=AsyncMock(return_value=resp_mock)),
            patch("orchestrator.search.core.embedding.llm_settings", settings_mock),
        ):
            result = await QueryEmbedder.generate_for_text_async("hello world")

        # EMBEDDING_DIMENSION=3, so we expect first 3 values
        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_input_is_lowercased(self):
        settings_mock = _make_settings_mock()
        resp_mock = MagicMock()
        resp_mock.data = [{"embedding": [0.1, 0.2, 0.3]}]
        mock_aembed = AsyncMock(return_value=resp_mock)

        with (
            patch("orchestrator.search.core.embedding.llm_aembedding", new=mock_aembed),
            patch("orchestrator.search.core.embedding.llm_settings", settings_mock),
        ):
            await QueryEmbedder.generate_for_text_async("UPPERCASE TEXT")

        call_kwargs = mock_aembed.call_args.kwargs
        assert call_kwargs["input"] == ["uppercase text"]


class TestQueryEmbedderException:
    @pytest.mark.asyncio
    async def test_exception_returns_empty_list(self):
        settings_mock = _make_settings_mock()

        with (
            patch("orchestrator.search.core.embedding.llm_aembedding", new=AsyncMock(side_effect=RuntimeError("fail"))),
            patch("orchestrator.search.core.embedding.llm_settings", settings_mock),
        ):
            result = await QueryEmbedder.generate_for_text_async("some text")

        assert result == []
