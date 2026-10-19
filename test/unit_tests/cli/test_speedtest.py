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

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from orchestrator.core.cli.search import speedtest
from orchestrator.core.search.core.types import RetrieverType

UUID_TEXT = "3f2b8c1e-9d4a-4c1b-8e7f-1a2b3c4d5e6f"


@pytest.mark.parametrize(
    "query_text,retriever,expected",
    [
        ("network", None, True),
        ("network", RetrieverType.HYBRID, True),
        ("network", RetrieverType.SEMANTIC, True),
        ("network", RetrieverType.FUZZY, False),
        (UUID_TEXT, None, False),
    ],
)
def test_embedding_needed_per_retriever(query_text, retriever, expected):
    assert speedtest.Retriever.needs_embedding(speedtest.build_query(query_text, retriever)) is expected


@pytest.mark.parametrize("retriever", [None, *RetrieverType])
async def test_run_single_query_passes_retriever_and_embedding(retriever):
    response = MagicMock(results=[1, 2])
    response.metadata.search_type = "hybrid"
    execute = AsyncMock(return_value=response)

    @asynccontextmanager
    async def fake_session():
        yield MagicMock()

    with (
        patch.object(speedtest.engine, "execute_search", execute),
        patch.object(speedtest.db, "async_session", fake_session),
    ):
        await speedtest.run_single_query("network", {"network": [0.1]}, retriever)

    expected_embedding = None if retriever == RetrieverType.FUZZY else [0.1]
    assert execute.call_args.kwargs["query"].retriever == retriever
    assert execute.call_args.kwargs["query_embedding"] == expected_embedding


@pytest.mark.parametrize("retriever", [None, RetrieverType.HYBRID, RetrieverType.SEMANTIC])
async def test_run_single_query_raises_when_embedding_missing(retriever):
    execute = AsyncMock()

    with (
        patch.object(speedtest.engine, "execute_search", execute),
        pytest.raises(ValueError, match="Embedding unavailable for query 'network'"),
    ):
        await speedtest.run_single_query("network", {}, retriever)

    execute.assert_not_awaited()


@pytest.mark.parametrize(
    "args,expected_retriever,expected_embedded",
    [
        ([], None, ["network"]),
        (["--retriever", "fuzzy"], RetrieverType.FUZZY, []),
        (["-r", "semantic"], RetrieverType.SEMANTIC, ["network"]),
        (["-r", "hybrid"], RetrieverType.HYBRID, ["network"]),
    ],
)
def test_quick_retriever_option(args, expected_retriever, expected_embedded):
    run_single = AsyncMock(return_value={"query": "network", "time": 0.01, "results": 1, "search_type": "x"})
    embed = AsyncMock(return_value={})

    with (
        patch.object(speedtest, "run_single_query", run_single),
        patch.object(speedtest, "generate_embeddings_for_queries", embed),
    ):
        result = CliRunner().invoke(speedtest.app, ["-q", "network", *args])

    assert result.exit_code == 0, result.output
    embed.assert_awaited_once_with(expected_embedded)
    assert run_single.call_args.args[2] == expected_retriever


def test_quick_rejects_unknown_retriever():
    result = CliRunner().invoke(speedtest.app, ["-q", "network", "-r", "bogus"])

    assert result.exit_code != 0
