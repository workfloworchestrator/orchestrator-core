import logging

import structlog
from litellm import aembedding as llm_aembedding
from litellm import embedding as llm_embedding
from litellm import exceptions as llm_exc

from orchestrator.settings import app_settings

logger = structlog.get_logger(__name__)

# Its logging alot of noise such as embedding vectors.
logging.getLogger("LiteLLM").setLevel(logging.WARNING)


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
                model=app_settings.EMBEDDING_MODEL,
                input=[t.lower() for t in texts],
                api_key=app_settings.OPENAI_API_KEY,
                base_url=app_settings.OPENAI_BASE_URL,
                timeout=app_settings.LLM_TIMEOUT,
                max_retries=app_settings.LLM_MAX_RETRIES,
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
                model=app_settings.EMBEDDING_MODEL,
                input=[text.lower()],
                api_key=app_settings.OPENAI_API_KEY,
                base_url=app_settings.OPENAI_BASE_URL,
                timeout=app_settings.LLM_TIMEOUT,
                max_retries=app_settings.LLM_MAX_RETRIES,
            )
            return resp.data[0]["embedding"]
        except Exception as e:
            logger.error("Async embedding generation failed", error=str(e))
            return []
