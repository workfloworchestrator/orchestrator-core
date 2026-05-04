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

"""Tests for EmbeddingIndexer and QueryEmbedder embedding generation logic.

Covers batch embedding, dry-run mode, truncation, sorting, error handling,
and async query embedding.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import litellm.exceptions as llm_exc
import pytest

from orchestrator.core.search.core.embedding import EmbeddingIndexer, QueryEmbedder

pytestmark = pytest.mark.search

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_SETTINGS = {
    "EMBEDDING_MODEL": "openai/text-embedding-3-small",
    "EMBEDDING_API_KEY": "test-key",
    "EMBEDDING_API_BASE": None,
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
# EmbeddingIndexer — empty / dry-run
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texts", "dry_run"),
    [
        pytest.param([], False, id="empty_list"),
        pytest.param([], True, id="empty_list_dry_run"),
    ],
)
def test_embedding_indexer_empty_list_returns_empty(texts, dry_run):
    result = EmbeddingIndexer.get_embeddings_from_api_batch(texts, dry_run=dry_run)
    assert result == []


@pytest.mark.parametrize(
    "texts",
    [
        pytest.param(["hello"], id="single"),
        pytest.param(["hello", "world"], id="two"),
        pytest.param(["a", "b", "c", "d"], id="four"),
    ],
)
def test_embedding_indexer_dry_run_returns_empty_list_per_text(texts):
    result = EmbeddingIndexer.get_embeddings_from_api_batch(texts, dry_run=True)
    assert result == [[] for _ in texts]


# ---------------------------------------------------------------------------
# EmbeddingIndexer — success
# ---------------------------------------------------------------------------


def test_embedding_indexer_successful_batch_returns_truncated():
    settings_mock = _make_settings_mock()
    raw_embeddings = [[0.1, 0.2, 0.3, 0.4, 0.5], [0.6, 0.7, 0.8, 0.9, 1.0]]
    resp_mock = _make_embedding_response(raw_embeddings)

    with (
        patch("orchestrator.core.search.core.embedding.llm_embedding", return_value=resp_mock),
        patch("orchestrator.core.search.core.embedding.llm_settings", settings_mock),
    ):
        result = EmbeddingIndexer.get_embeddings_from_api_batch(["hello", "world"], dry_run=False)

    assert result == [[0.1, 0.2, 0.3], [0.6, 0.7, 0.8]]


@pytest.mark.parametrize(
    ("resp_data", "expected"),
    [
        pytest.param(
            [{"index": 1, "embedding": [0.9, 0.8, 0.7, 0.6]}, {"index": 0, "embedding": [0.1, 0.2, 0.3, 0.4]}],
            [[0.1, 0.2, 0.3], [0.9, 0.8, 0.7]],
            id="reversed_order",
        ),
        pytest.param(
            [{"index": 0, "embedding": [0.1, 0.2, 0.3, 0.4]}, {"index": 1, "embedding": [0.9, 0.8, 0.7, 0.6]}],
            [[0.1, 0.2, 0.3], [0.9, 0.8, 0.7]],
            id="already_sorted",
        ),
    ],
)
def test_embedding_indexer_sorts_by_index(resp_data, expected):
    """Response data must be sorted by index before returning, regardless of order."""
    settings_mock = _make_settings_mock()
    resp = MagicMock()
    resp.data = resp_data

    with (
        patch("orchestrator.core.search.core.embedding.llm_embedding", return_value=resp),
        patch("orchestrator.core.search.core.embedding.llm_settings", settings_mock),
    ):
        result = EmbeddingIndexer.get_embeddings_from_api_batch(["first", "second"], dry_run=False)

    assert result == expected


def test_embedding_indexer_inputs_are_lowercased():
    settings_mock = _make_settings_mock()
    resp_mock = _make_embedding_response([[0.1, 0.2, 0.3]])

    with (
        patch("orchestrator.core.search.core.embedding.llm_embedding", return_value=resp_mock) as mock_embed,
        patch("orchestrator.core.search.core.embedding.llm_settings", settings_mock),
    ):
        EmbeddingIndexer.get_embeddings_from_api_batch(["HELLO"], dry_run=False)

    call_kwargs = mock_embed.call_args.kwargs
    assert call_kwargs["input"] == ["hello"]


# ---------------------------------------------------------------------------
# EmbeddingIndexer — API errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(
            llm_exc.APIError(500, "server error", "openai", "test-model", request=httpx.Request("GET", "http://x")),
            id="api_error",
        ),
        pytest.param(
            llm_exc.APIConnectionError("connection failed", "openai", "test-model"),
            id="connection_error",
        ),
        pytest.param(
            llm_exc.RateLimitError("rate limited", llm_provider="openai", model="test-model"),
            id="rate_limit",
        ),
        pytest.param(
            llm_exc.Timeout("timed out", model="test-model", llm_provider="openai"),
            id="timeout",
        ),
    ],
)
def test_embedding_indexer_known_api_errors_return_empty(exception):
    settings_mock = _make_settings_mock()
    texts = ["hello", "world"]

    with (
        patch("orchestrator.core.search.core.embedding.llm_embedding", side_effect=exception),
        patch("orchestrator.core.search.core.embedding.llm_settings", settings_mock),
    ):
        result = EmbeddingIndexer.get_embeddings_from_api_batch(texts, dry_run=False)

    assert result == [[], []]


def test_embedding_indexer_unexpected_error_returns_empty():
    settings_mock = _make_settings_mock()
    texts = ["a", "b", "c"]

    with (
        patch("orchestrator.core.search.core.embedding.llm_embedding", side_effect=RuntimeError("boom")),
        patch("orchestrator.core.search.core.embedding.llm_settings", settings_mock),
    ):
        result = EmbeddingIndexer.get_embeddings_from_api_batch(texts, dry_run=False)

    assert result == [[], [], []]


# ---------------------------------------------------------------------------
# QueryEmbedder — empty / None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        pytest.param("", id="empty_string"),
        pytest.param(None, id="none"),
    ],
)
async def test_query_embedder_empty_or_none_returns_empty(text):
    result = await QueryEmbedder.generate_for_text_async(text)
    assert result is None


# ---------------------------------------------------------------------------
# QueryEmbedder — success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_embedder_returns_truncated_embedding():
    settings_mock = _make_settings_mock()
    raw_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    resp_mock = MagicMock()
    resp_mock.data = [{"embedding": raw_embedding}]

    with (
        patch("orchestrator.core.search.core.embedding.llm_aembedding", new=AsyncMock(return_value=resp_mock)),
        patch("orchestrator.core.search.core.embedding.llm_settings", settings_mock),
    ):
        result = await QueryEmbedder.generate_for_text_async("hello world")

    assert result == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_query_embedder_input_is_lowercased():
    settings_mock = _make_settings_mock()
    resp_mock = MagicMock()
    resp_mock.data = [{"embedding": [0.1, 0.2, 0.3]}]
    mock_aembed = AsyncMock(return_value=resp_mock)

    with (
        patch("orchestrator.core.search.core.embedding.llm_aembedding", new=mock_aembed),
        patch("orchestrator.core.search.core.embedding.llm_settings", settings_mock),
    ):
        await QueryEmbedder.generate_for_text_async("UPPERCASE TEXT")

    call_kwargs = mock_aembed.call_args.kwargs
    assert call_kwargs["input"] == ["uppercase text"]


# ---------------------------------------------------------------------------
# QueryEmbedder — exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_embedder_exception_returns_none():
    settings_mock = _make_settings_mock()

    with (
        patch(
            "orchestrator.core.search.core.embedding.llm_aembedding", new=AsyncMock(side_effect=RuntimeError("fail"))
        ),
        patch("orchestrator.core.search.core.embedding.llm_settings", settings_mock),
    ):
        result = await QueryEmbedder.generate_for_text_async("some text")

    assert result is None
