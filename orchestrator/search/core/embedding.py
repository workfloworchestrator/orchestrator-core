import os
from typing import List, Optional

import openai
import structlog
from openai import OpenAI

from orchestrator.settings import app_settings

from .types import ExtractedField

logger = structlog.get_logger(__name__)


class EmbeddingGenerator:
    """Handles the creation of vector embeddings from structured data.

    This class provides methods for converting structured data into text
    and generating embeddings via the OpenAI API.
    """

    _client: Optional[OpenAI] = None

    @classmethod
    def _get_client(cls) -> OpenAI:
        """Get or create a shared OpenAI client instance.

        Returns:
            OpenAI: An initialized OpenAI API client.
        """

        if cls._client is None:
            base_url = os.environ.get("OPENAI_BASE_URL")
            api_key = os.environ.get("OPENAI_API_KEY")

            cls._client = OpenAI(api_key=api_key, base_url=base_url)
        return cls._client

    @classmethod
    def _create_filtered_document(cls, fields: List[ExtractedField]) -> str:
        """Convert embeddable fields into a clean text document.

        Args:
            fields (List[ExtractedField]): A list of extracted fields.

        Returns:
            str: A newline-separated string containing paths and lowercased values
            for embeddable fields only.
        """
        document_lines = [
            f"{field.path}: {field.value.lower()}" for field in fields if field.value_type.is_embeddable()
        ]
        return "\n".join(document_lines)

    @classmethod
    def _get_embedding_from_api(cls, text: str) -> List[float]:
        """Generate a vector embedding for a given text.

        Args:
            text (str): The text to embed.

        Returns:
            List[float]: The generated embedding vector, or an empty list if
            the text is empty or an error occurs.
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
        """Generate an embedding from a list of extracted fields.

        Args:
            fields (List[ExtractedField]): Fields to include in the embedding.
            dry_run (bool, optional): If True, log the document without calling
                the API. Defaults to False.

        Returns:
            List[float]: The embedding vector, or an empty list if dry_run is True
            or an error occurs.
        """
        document = cls._create_filtered_document(fields)

        if dry_run:
            logger.info(f"Dry Run: Would have requested embeddings for:\n{document}")
            return []
        return cls._get_embedding_from_api(document)

    @classmethod
    def _get_embeddings_from_api_batch(cls, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts in a single API call.

        Args:
            texts (List[str]): A list of text strings to embed.

        Returns:
            List[List[float]]: A list of embedding vectors, in the same order as input.
            Returns empty lists for failed embeddings.
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
        """Generate embeddings for multiple texts.

        Args:
            texts (List[str]): The list of texts to embed.
            dry_run (bool, optional): If True, return empty embeddings without
                calling the API. Defaults to False.

        Returns:
            List[List[float]]: A list of embedding vectors for each text.
        """
        if dry_run:
            return [[] for _ in texts]
        return cls._get_embeddings_from_api_batch(texts)

    @classmethod
    def generate_for_text(cls, text: str, dry_run: bool = False) -> List[float]:
        """Generate an embedding from a single text string.

        Args:
            text (str): The text to embed.
            dry_run (bool, optional): If True, log the text without calling
                the API. Defaults to False.

        Returns:
            List[float]: The embedding vector, or an empty list if dry_run is True
            or an error occurs.
        """
        normalized_text = text.lower()
        if dry_run:
            logger.info(f"Dry Run: Would have requested embeddings for:\n{text}")
            return []
        return cls._get_embedding_from_api(normalized_text)
