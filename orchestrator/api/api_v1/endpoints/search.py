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

from typing import Any, Literal, overload

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import case, select
from sqlalchemy.orm import selectinload

from orchestrator.db import (
    ProcessTable,
    ProductTable,
    WorkflowTable,
    db,
)
from orchestrator.domain.base import SubscriptionModel
from orchestrator.schemas.search import (
    PageInfoSchema,
    PathsResponse,
    ProcessSearchResult,
    ProcessSearchSchema,
    ProductSearchResult,
    ProductSearchSchema,
    SearchResultsSchema,
    SubscriptionSearchResult,
    WorkflowSearchResult,
    WorkflowSearchSchema,
)
from orchestrator.search.core.exceptions import InvalidCursorError
from orchestrator.search.core.types import EntityType, UIType
from orchestrator.search.filters.definitions import generate_definitions
from orchestrator.search.indexing.registry import ENTITY_CONFIG_REGISTRY
from orchestrator.search.retrieval import execute_search
from orchestrator.search.retrieval.builder import build_paths_query, create_path_autocomplete_lquery, process_path_rows
from orchestrator.search.retrieval.pagination import (
    create_next_page_cursor,
    process_pagination_cursor,
)
from orchestrator.search.retrieval.validation import is_lquery_syntactically_valid
from orchestrator.search.schemas.parameters import (
    BaseSearchParameters,
    ProcessSearchParameters,
    ProductSearchParameters,
    SubscriptionSearchParameters,
    WorkflowSearchParameters,
)
from orchestrator.search.schemas.results import SearchResult, TypeDefinition
from orchestrator.services.subscriptions import format_special_types

router = APIRouter()


def _create_search_result_item(
    entity: WorkflowTable | ProductTable | ProcessTable, entity_type: EntityType, search_info: SearchResult
) -> WorkflowSearchResult | ProductSearchResult | ProcessSearchResult | None:
    match entity_type:
        case EntityType.WORKFLOW:
            workflow_data = WorkflowSearchSchema.model_validate(entity)
            return WorkflowSearchResult(
                workflow=workflow_data,
                score=search_info.score,
                perfect_match=search_info.perfect_match,
                matching_field=search_info.matching_field,
            )
        case EntityType.PRODUCT:
            product_data = ProductSearchSchema.model_validate(entity)
            return ProductSearchResult(
                product=product_data,
                score=search_info.score,
                perfect_match=search_info.perfect_match,
                matching_field=search_info.matching_field,
            )
        case EntityType.PROCESS:
            process_data = ProcessSearchSchema.model_validate(entity)
            return ProcessSearchResult(
                process=process_data,
                score=search_info.score,
                perfect_match=search_info.perfect_match,
                matching_field=search_info.matching_field,
            )
        case _:
            return None


@overload
async def _perform_search_and_fetch(
    search_params: BaseSearchParameters,
    entity_type: Literal[EntityType.WORKFLOW],
    eager_loads: list[Any],
    cursor: str | None = None,
) -> SearchResultsSchema[WorkflowSearchResult]: ...


@overload
async def _perform_search_and_fetch(
    search_params: BaseSearchParameters,
    entity_type: Literal[EntityType.PRODUCT],
    eager_loads: list[Any],
    cursor: str | None = None,
) -> SearchResultsSchema[ProductSearchResult]: ...


@overload
async def _perform_search_and_fetch(
    search_params: BaseSearchParameters,
    entity_type: Literal[EntityType.PROCESS],
    eager_loads: list[Any],
    cursor: str | None = None,
) -> SearchResultsSchema[ProcessSearchResult]: ...


async def _perform_search_and_fetch(
    search_params: BaseSearchParameters,
    entity_type: EntityType,
    eager_loads: list[Any],
    cursor: str | None = None,
) -> SearchResultsSchema[Any]:
    try:
        pagination_params = await process_pagination_cursor(cursor, search_params)
    except InvalidCursorError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid pagination cursor")

    search_response = await execute_search(
        search_params=search_params,
        db_session=db.session,
        pagination_params=pagination_params,
    )
    if not search_response.results:
        return SearchResultsSchema(search_metadata=search_response.metadata)

    next_page_cursor = create_next_page_cursor(search_response.results, pagination_params, search_params.limit)
    has_next_page = next_page_cursor is not None
    page_info = PageInfoSchema(has_next_page=has_next_page, next_page_cursor=next_page_cursor)

    config = ENTITY_CONFIG_REGISTRY[entity_type]
    entity_ids = [res.entity_id for res in search_response.results]
    pk_column = getattr(config.table, config.pk_name)
    ordering_case = case({entity_id: i for i, entity_id in enumerate(entity_ids)}, value=pk_column)

    stmt = select(config.table).options(*eager_loads).filter(pk_column.in_(entity_ids)).order_by(ordering_case)
    entities = db.session.scalars(stmt).all()

    search_info_map = {res.entity_id: res for res in search_response.results}
    data = []
    for entity in entities:
        entity_id = getattr(entity, config.pk_name)
        search_info = search_info_map.get(str(entity_id))
        if not search_info:
            continue

        search_result_item = _create_search_result_item(entity, entity_type, search_info)
        if search_result_item:
            data.append(search_result_item)

    return SearchResultsSchema(data=data, page_info=page_info, search_metadata=search_response.metadata)


@router.post(
    "/subscriptions",
    response_model=SearchResultsSchema[SubscriptionSearchResult],
)
async def search_subscriptions(
    search_params: SubscriptionSearchParameters,
    cursor: str | None = None,
) -> SearchResultsSchema[SubscriptionSearchResult]:
    try:
        pagination_params = await process_pagination_cursor(cursor, search_params)
    except InvalidCursorError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid pagination cursor")

    search_response = await execute_search(
        search_params=search_params,
        db_session=db.session,
        pagination_params=pagination_params,
    )

    if not search_response.results:
        return SearchResultsSchema(search_metadata=search_response.metadata)

    next_page_cursor = create_next_page_cursor(search_response.results, pagination_params, search_params.limit)
    has_next_page = next_page_cursor is not None
    page_info = PageInfoSchema(has_next_page=has_next_page, next_page_cursor=next_page_cursor)

    search_info_map = {res.entity_id: res for res in search_response.results}
    results_data = []
    for sub_id, search_info in search_info_map.items():
        subscription_model = SubscriptionModel.from_subscription(sub_id)
        sub_data = subscription_model.model_dump(exclude_unset=False)
        search_result_item = SubscriptionSearchResult(
            subscription=format_special_types(sub_data),
            score=search_info.score,
            perfect_match=search_info.perfect_match,
            matching_field=search_info.matching_field,
        )
        results_data.append(search_result_item)

    return SearchResultsSchema(data=results_data, page_info=page_info, search_metadata=search_response.metadata)


@router.post("/workflows", response_model=SearchResultsSchema[WorkflowSearchResult])
async def search_workflows(
    search_params: WorkflowSearchParameters,
    cursor: str | None = None,
) -> SearchResultsSchema[WorkflowSearchResult]:
    return await _perform_search_and_fetch(
        search_params=search_params,
        entity_type=EntityType.WORKFLOW,
        eager_loads=[selectinload(WorkflowTable.products)],
        cursor=cursor,
    )


@router.post("/products", response_model=SearchResultsSchema[ProductSearchResult])
async def search_products(
    search_params: ProductSearchParameters,
    cursor: str | None = None,
) -> SearchResultsSchema[ProductSearchResult]:
    return await _perform_search_and_fetch(
        search_params=search_params,
        entity_type=EntityType.PRODUCT,
        eager_loads=[
            selectinload(ProductTable.workflows),
            selectinload(ProductTable.fixed_inputs),
            selectinload(ProductTable.product_blocks),
        ],
        cursor=cursor,
    )


@router.post("/processes", response_model=SearchResultsSchema[ProcessSearchResult])
async def search_processes(
    search_params: ProcessSearchParameters,
    cursor: str | None = None,
) -> SearchResultsSchema[ProcessSearchResult]:
    return await _perform_search_and_fetch(
        search_params=search_params,
        entity_type=EntityType.PROCESS,
        eager_loads=[
            selectinload(ProcessTable.workflow),
        ],
        cursor=cursor,
    )


@router.get(
    "/paths",
    response_model=PathsResponse,
    response_model_exclude_none=True,
)
async def list_paths(
    prefix: str = Query("", min_length=0),
    q: str | None = Query(None, description="Query for path suggestions"),
    entity_type: EntityType = Query(EntityType.SUBSCRIPTION),
    limit: int = Query(10, ge=1, le=10),
) -> PathsResponse:

    if prefix:
        lquery_pattern = create_path_autocomplete_lquery(prefix)

        if not is_lquery_syntactically_valid(lquery_pattern, db.session):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Prefix '{prefix}' creates an invalid search pattern.",
            )
    stmt = build_paths_query(entity_type=entity_type, prefix=prefix, q=q)
    stmt = stmt.limit(limit)
    rows = db.session.execute(stmt).all()

    leaves, components = process_path_rows(rows)
    return PathsResponse(leaves=leaves, components=components)


@router.get(
    "/definitions",
    response_model=dict[UIType, TypeDefinition],
    response_model_exclude_none=True,
)
async def get_definitions() -> dict[UIType, TypeDefinition]:
    """Provide a static definition of operators and schemas for each UI type."""
    return generate_definitions()
