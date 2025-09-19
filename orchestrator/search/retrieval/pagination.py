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

import array
import base64
from dataclasses import dataclass

from pydantic import BaseModel

from orchestrator.search.core.exceptions import InvalidCursorError
from orchestrator.search.schemas.parameters import BaseSearchParameters
from orchestrator.search.schemas.results import SearchResult


@dataclass
class PaginationParams:
    """Parameters for pagination in search queries."""

    page_after_score: float | None = None
    page_after_id: str | None = None
    q_vec_override: list[float] | None = None


def floats_to_b64(v: list[float]) -> str:
    a = array.array("f", v)
    return base64.urlsafe_b64encode(a.tobytes()).decode("ascii")


def b64_to_floats(s: str) -> list[float]:
    raw = base64.urlsafe_b64decode(s.encode("ascii"))
    a = array.array("f")
    a.frombytes(raw)
    return list(a)


class PageCursor(BaseModel):
    score: float
    id: str
    q_vec_b64: str

    def encode(self) -> str:
        """Encode the cursor data into a URL-safe Base64 string."""
        json_str = self.model_dump_json()
        return base64.urlsafe_b64encode(json_str.encode("utf-8")).decode("utf-8")

    @classmethod
    def decode(cls, cursor: str) -> "PageCursor":
        """Decode a Base64 string back into a PageCursor instance."""
        try:
            decoded_str = base64.urlsafe_b64decode(cursor).decode("utf-8")
            return cls.model_validate_json(decoded_str)
        except Exception as e:
            raise InvalidCursorError("Invalid pagination cursor") from e


async def process_pagination_cursor(cursor: str | None, search_params: BaseSearchParameters) -> PaginationParams:
    """Process pagination cursor and return pagination parameters."""
    if cursor:
        c = PageCursor.decode(cursor)
        return PaginationParams(
            page_after_score=c.score,
            page_after_id=c.id,
            q_vec_override=b64_to_floats(c.q_vec_b64),
        )
    if search_params.vector_query:
        from orchestrator.search.core.embedding import QueryEmbedder

        q_vec_override = await QueryEmbedder.generate_for_text_async(search_params.vector_query)
        return PaginationParams(q_vec_override=q_vec_override)
    return PaginationParams()


def create_next_page_cursor(
    search_results: list[SearchResult], pagination_params: PaginationParams, limit: int
) -> str | None:
    """Create next page cursor if there are more results."""
    has_next_page = len(search_results) == limit and limit > 0
    if has_next_page:
        last_item = search_results[-1]
        cursor_data = PageCursor(
            score=float(last_item.score),
            id=last_item.entity_id,
            q_vec_b64=floats_to_b64(pagination_params.q_vec_override or []),
        )
        return cursor_data.encode()
    return None
