from typing import List, Optional, Tuple

from pydantic import BaseModel


class Highlight(BaseModel):
    """Contains the text and the indices of the matched term."""

    text: str
    indices: List[Tuple[int, int]]


class SearchResult(BaseModel):
    """Represents a single search result item."""

    entity_id: str
    score: float
    highlight: Optional[Highlight] = None


SearchResponse = List[SearchResult]
