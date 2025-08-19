from pydantic import BaseModel


class Highlight(BaseModel):
    """Contains the text and the indices of the matched term."""

    text: str
    indices: list[tuple[int, int]]


class SearchResult(BaseModel):
    """Represents a single search result item."""

    entity_id: str
    score: float
    highlight: Highlight | None = None


SearchResponse = list[SearchResult]
