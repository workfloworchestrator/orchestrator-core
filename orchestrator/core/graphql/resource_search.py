# Copyright 2019-2026 SURF, GÉANT.
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

"""Search on GraphQL list resources: the `search` argument of e.g. `subscriptions`.

Runs the search and pairs its hits with entities the resource resolvers load.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import TypeVar, cast
from uuid import UUID

import structlog
from graphql import GraphQLError
from strawberry.types.nodes import SelectedField

from nwastdlib.graphql.extensions.error_handler_extension import EXTENSION_ERROR_TYPE, ErrorType
from orchestrator.core.graphql.pagination import Connection, PageInfo, SearchEdge
from orchestrator.core.graphql.schemas.search import MatchingFieldType, SearchMetadataType
from orchestrator.core.graphql.search_inputs import ResourceSearchInput
from orchestrator.core.graphql.types import OrchestratorInfo
from orchestrator.core.search.core.exceptions import InvalidCursorError, QueryStateNotFoundError
from orchestrator.core.search.core.types import EntityType, SearchMetadata
from orchestrator.core.search.query.page import SearchPage, execute_search_page
from orchestrator.core.search.query.results import MatchingField, SearchResult

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def matching_field_to_gql(mf: MatchingField) -> MatchingFieldType:
    """Convert a domain MatchingField to its GraphQL type."""
    return MatchingFieldType(
        text=mf.text,
        path=mf.path,
        highlight_indices=mf.highlight_indices,
    )


def metadata_to_gql(metadata: SearchMetadata) -> SearchMetadataType:
    """Convert a domain SearchMetadata to its Strawberry GraphQL type."""
    return SearchMetadataType(
        search_type=metadata.search_type,
        description=metadata.description,
    )


# GraphQL names of the list-resource arguments that `search` replaces.
_NON_SEARCH_ARGUMENTS = frozenset({"filterBy", "sortBy", "query"})


def _reject_non_search_arguments(info: OrchestratorInfo) -> None:
    """Raise when `search` is combined with the resource's own filter and sort arguments.

    Reads sent arguments from the query, as the resolver only sees values after defaults. A field selected more than
    once without an alias is resolved once with all its selections; GraphQL only merges them when their arguments are
    equal, so any of them shows what was sent.
    """
    fields = cast(list[SelectedField], info.selected_fields)
    sent = {name for field in fields for name, value in field.arguments.items() if value is not None}
    if conflicting := sorted(sent & _NON_SEARCH_ARGUMENTS):
        raise _client_error(f"'search' cannot be combined with {', '.join(conflicting)}", ErrorType.BAD_REQUEST)


def _client_error(message: str, error_type: ErrorType) -> GraphQLError:
    """GraphQLError the client can act on.

    Without a non-internal `error_type`, ErrorHandlerExtension masks the message as "Internal Server Error",
    hiding why the search was rejected.
    """
    code = "NOT_FOUND" if error_type == ErrorType.NOT_FOUND else "VALIDATION_ERROR"
    return GraphQLError(message, extensions={"code": code, EXTENSION_ERROR_TYPE: str(error_type)})


async def execute_resource_search(
    info: OrchestratorInfo, entity_type: EntityType, search: ResourceSearchInput, first: int, after: int
) -> SearchPage:
    """Run the `search` argument of a list resource and return the ranked hits.

    `first` is the page size; `after` skips hits, structured search only.
    `search.entity_ids` isn't saved with the query, so pass it on every page, cursor pages included.

    Raises:
        GraphQLError: When `search` is combined with other arguments, or the search itself fails.
    """
    _reject_non_search_arguments(info)
    try:
        page = await execute_search_page(
            info.context.session,
            query=None if search.cursor else search.to_select_query(entity_type, first),
            cursor=search.cursor,
            entity_type=entity_type,
            entity_ids=search.entity_ids,
            offset=after,
        )
    except (InvalidCursorError, ValueError) as e:
        raise _client_error(str(e), ErrorType.BAD_REQUEST) from e
    except QueryStateNotFoundError as e:
        raise _client_error(str(e), ErrorType.NOT_FOUND) from e
    except Exception as e:
        logger.error("Resource search failed", entity_type=entity_type, error=str(e))
        raise GraphQLError(f"Search failed: {e}", extensions={"code": "INTERNAL_ERROR"}) from e
    return page


def _search_edge(result: SearchResult, node: T) -> SearchEdge[T]:
    return SearchEdge(
        node=node,
        score=result.score,
        perfect_match=result.perfect_match,
        matching_fields=[matching_field_to_gql(mf) for mf in result.matching_fields],
    )


def to_search_connection(
    search_page: SearchPage, nodes_by_id: Mapping[str, T], *, has_previous_page: bool
) -> Connection[T]:
    """Pair each hit with its loaded entity, keeping the search ranking.

    Hits without an entity are skipped: the search index can lag behind deletions.
    """
    response = search_page.response
    edges = [
        _search_edge(result, nodes_by_id[result.entity_id])
        for result in response.results
        if result.entity_id in nodes_by_id
    ]
    return Connection(
        page_info=PageInfo(
            has_previous_page=has_previous_page,
            has_next_page=search_page.next_page_cursor is not None,
            start_cursor=response.start_cursor,
            end_cursor=response.end_cursor,
            total_items=response.total_items,
            sort_fields=[],
            filter_fields=[],
        ),
        search_edges=edges,
        search_metadata=metadata_to_gql(response.metadata),
        next_page_cursor=search_page.next_page_cursor,
        page=[edge.node for edge in edges],
    )


async def search_resource(
    info: OrchestratorInfo,
    entity_type: EntityType,
    search: ResourceSearchInput,
    load_nodes: Callable[[OrchestratorInfo, Sequence[UUID]], Awaitable[Mapping[str, T]]],
    *,
    first: int,
    after: int,
) -> Connection[T]:
    """Run the `search` argument of a list resource and load its hits with `load_nodes`.

    `load_nodes` gets `info` and the hit ids and returns their GraphQL nodes keyed by id as string; it is not called
    when there are no hits.
    """
    search_page = await execute_resource_search(info, entity_type, search, first, after)
    entity_ids = [UUID(entity_id) for entity_id in search_page.entity_ids]
    nodes_by_id = await load_nodes(info, entity_ids) if entity_ids else {}
    has_previous_page = bool(after) or search.cursor is not None
    return to_search_connection(search_page, nodes_by_id, has_previous_page=has_previous_page)
