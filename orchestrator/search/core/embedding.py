from typing import List, Optional
from .types import ExtractedField
from orchestrator.settings import app_settings
import os
import structlog
import openai
from openai import OpenAI

logger = structlog.get_logger(__name__)


class EmbeddingGenerator:
    """
    A class to handle the creation of vector embeddings from structured data.

    This class encapsulates the logic for filtering noisy data and interacting
    with an embedding model API.
    """

    _client: Optional[OpenAI] = None

    @classmethod
    def _get_client(cls) -> OpenAI:
        """
        Returns a shared OpenAI client instance, creating it if it doesn't exist.
        """
        if cls._client is None:
            base_url = os.environ.get("OPENAI_BASE_URL")
            api_key = os.environ.get("OPENAI_API_KEY")

            cls._client = OpenAI(api_key=api_key, base_url=base_url)
        return cls._client

    @classmethod
    def _create_filtered_document(cls, fields: List[ExtractedField]) -> str:
        """
        Serializes embeddable fields into a clean text document.
        """
        document_lines = [
            f"{field.path}: {field.value.lower()}" for field in fields if field.value_type.is_embeddable()
        ]
        return "\n".join(document_lines)

    @classmethod
    def _get_embedding_from_api(cls, text: str) -> List[float]:
        """
        Generates a vector embedding for a given text document using the OpenAI API.
        """
        if not text:
            return []

        try:
            response = cls._get_client().embeddings.create(input=[text], model=app_settings.embedding_model_name)
            return response.data[0].embedding
        except openai.APIStatusError as e:
            logger.error("OpenAI API returned a non-200 status code", status_code=e.status_code, response=e.response)
            return []
        except openai.APIConnectionError as e:
            logger.error("Failed to connect to OpenAI API", error=e.__cause__)
            return []
        except Exception as e:
            logger.error("An unexpected error occurred while generating embedding", error=str(e))
            return []

    @classmethod
    def generate_for_fields(cls, fields: List[ExtractedField], dry_run: bool = False) -> List[float]:
        """
        The main public method. Takes a list of fields, creates a filtered
        document, and returns the resulting vector embedding.
        """
        document = cls._create_filtered_document(fields)

        if dry_run:
            logger.info(f"Dry Run: Would have requested embeddings for:\n{document}")
            return []
        return cls._get_embedding_from_api(document)

    @classmethod
    def _get_embeddings_from_api_batch(cls, texts: List[str]) -> List[List[float]]:
        """
        Generates vector embeddings for a batch of texts using a single API call.
        Returns a list of embeddings in the same order as the input texts.
        """
        if not texts:
            return []

        try:
            response = cls._get_client().embeddings.create(input=texts, model=app_settings.embedding_model_name)
            sorted_embeddings = sorted(response.data, key=lambda e: e.index)
            return [data.embedding for data in sorted_embeddings]
        except openai.APIStatusError as e:
            logger.error("OpenAI API returned a non-200 status code", status_code=e.status_code, response=e.response)
            return [[] for _ in texts]  # Return empty lists for each text on failure
        except openai.APIConnectionError as e:
            logger.error("Failed to connect to OpenAI API", error=e.__cause__)
            return [[] for _ in texts]
        except Exception as e:
            logger.error("An unexpected error occurred during batch embedding", error=str(e))
            return [[] for _ in texts]

    @classmethod
    def generate_for_batch(cls, texts: List[str], dry_run: bool = False) -> List[List[float]]:
        """
        The main public method for batch processing. Takes a list of texts
        and returns a list of corresponding vector embeddings.
        """
        if dry_run:
            return [[] for _ in texts]
        return cls._get_embeddings_from_api_batch(texts)

    @classmethod
    def generate_for_text(cls, text: str, dry_run: bool = False) -> List[float]:
        """
        Creates an embedding from a pre-formatted string.
        Used for embedding LLM-generated queries or other raw text.
        """
        normalized_text = text.lower()
        if dry_run:
            logger.info(f"Dry Run: Would have requested embeddings for:\n{text}")
            return []
        return cls._get_embedding_from_api(normalized_text)
