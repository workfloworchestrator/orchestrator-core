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


import structlog
from litellm import aembedding as llm_aembedding
from litellm import embedding as llm_embedding
from litellm import exceptions as llm_exc

from orchestrator.llm_settings import llm_settings

logger = structlog.get_logger(__name__)


class EmbeddingIndexer:

    @classmethod
    def get_embeddings_from_api_batch(cls, texts: list[str], dry_run: bool) -> list[list[float]]:
        if not texts:
            return []
        if dry_run:
            logger.debug("Dry Run: returning empty embeddings")
            return [[] for _ in texts]

        try:
            resp = llm_embedding(
                model=llm_settings.EMBEDDING_MODEL,
                input=[t.lower() for t in texts],
                api_key=llm_settings.OPENAI_API_KEY,
                api_base=llm_settings.OPENAI_BASE_URL,
                timeout=llm_settings.LLM_TIMEOUT,
                max_retries=llm_settings.LLM_MAX_RETRIES,
            )
            data = sorted(resp.data, key=lambda e: e["index"])
            return [row["embedding"] for row in data]
        except (llm_exc.APIError, llm_exc.APIConnectionError, llm_exc.RateLimitError, llm_exc.Timeout) as e:
            logger.error("Embedding request failed", error=str(e))
            return [[] for _ in texts]
        except Exception as e:
            logger.error("Unexpected embedding error", error=str(e))
            return [[] for _ in texts]


class QueryEmbedder:
    """A stateless, async utility for embedding real-time user queries."""

    @classmethod
    async def generate_for_text_async(cls, text: str) -> list[float]:
        if not text:
            return []
        try:
            resp = await llm_aembedding(
                model=llm_settings.EMBEDDING_MODEL,
                input=[text.lower()],
                api_key=llm_settings.OPENAI_API_KEY,
                api_base=llm_settings.OPENAI_BASE_URL,
                timeout=5.0,
                max_retries=0,  # No retries, prioritize speed.
            )
            return resp.data[0]["embedding"]
        except Exception as e:
            logger.error("Async embedding generation failed", error=str(e))
            return []
