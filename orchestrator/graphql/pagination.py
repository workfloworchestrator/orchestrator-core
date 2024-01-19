# Copyright 2022-2023 SURF.
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
from typing import Any, Generic, TypeVar

import strawberry

GenericType = TypeVar("GenericType")


@strawberry.type(description="Represents a paginated relationship between two entities")
class Connection(Generic[GenericType]):
    """Represents a paginated relationship between two entities.

    This pattern is used when the relationship itself has attributes.
    In a Facebook-based domain example, a friendship between two people
    would be a connection that might have a `friendshipStartTime`
    """

    page_info: "PageInfo"
    page: list["GenericType"]


@strawberry.federation.type(
    shareable=True, description="Pagination context to navigate objects with cursor-based pagination"
)
class PageInfo:
    """Pagination context to navigate objects with cursor-based pagination.

    Instead of classic offset pagination via `page` and `limit` parameters,
    here we have a cursor of the last object and we fetch items starting from that one

    Read more at:
        - https://graphql.org/learn/pagination/#pagination-and-edges
        - https://relay.dev/graphql/connections.htm
    """

    has_next_page: bool
    has_previous_page: bool
    start_cursor: int | None
    end_cursor: int | None
    total_items: int | None
    sort_fields: list[str]
    filter_fields: list[str]


@strawberry.type(description="An edge may contain additional information of the relationship")
class Edge(Generic[GenericType]):
    """An edge may contain additional information of the relationship. This is the trivial case."""

    node: GenericType
    cursor: str


EMPTY_PAGE: Connection[Any] = Connection(
    page=[],
    page_info=PageInfo(
        has_previous_page=False,
        has_next_page=False,
        start_cursor=0,
        end_cursor=-1,
        total_items=0,
        sort_fields=[],
        filter_fields=[],
    ),
)
