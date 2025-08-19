from typing import Any

from pydantic import BaseModel, Field


class SearchState(BaseModel):
    parameters: dict[str, Any] | None = None
    results: list[dict[str, Any]] = Field(default_factory=list)
