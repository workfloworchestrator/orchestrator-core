from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchState(BaseModel):
    parameters: Optional[Dict[str, Any]] = None
    results: List[Dict[str, Any]] = Field(default_factory=list)
