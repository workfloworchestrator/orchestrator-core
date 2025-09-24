# Copyright 2019-2025 SURF
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
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from structlog import get_logger

logger = get_logger(__name__)


class LLMSettings(BaseSettings):
    LLM_ENABLED: bool = False  # Default to false
    # Pydantic-ai Agent settings
    AGENT_MODEL: str = "gpt-4o-mini"  # See pydantic-ai docs for supported models.
    AGENT_MODEL_VERSION: str = "2025-01-01-preview"
    OPENAI_API_KEY: str = ""  # Change per provider (Azure, etc).
    # Embedding settings
    EMBEDDING_DIMENSION: int = 1536
    EMBEDDING_MODEL: str = "openai/text-embedding-3-small"  # See litellm docs for supported models.
    EMBEDDING_SAFE_MARGIN_PERCENT: float = Field(
        0.1, description="Safety margin as a percentage (e.g., 0.1 for 10%) for token budgeting.", ge=0, le=1
    )

    # The following settings are only needed for local models.
    # By default, they are set conservative assuming a small model like All-MiniLM-L6-V2.
    OPENAI_BASE_URL: str | None = None
    EMBEDDING_FALLBACK_MAX_TOKENS: int | None = 512
    EMBEDDING_MAX_BATCH_SIZE: int | None = 32

    # General LiteLLM settings
    LLM_MAX_RETRIES: int = 3
    LLM_TIMEOUT: int = 30

    @field_validator("EMBEDDING_MODEL")
    def validate_embedding_model_format(cls, v: str) -> str:
        """Validate that embedding model is in 'vendor/model' format."""
        if "/" not in v:
            raise ValueError("EMBEDDING_MODEL must be in format 'vendor/model'")
        return v


llm_settings = LLMSettings()
