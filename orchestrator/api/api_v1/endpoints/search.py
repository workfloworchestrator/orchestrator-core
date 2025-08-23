from typing import Any, TypeVar, cast

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import case, select
from sqlalchemy.orm import selectinload

from orchestrator.db import (
    ProcessTable,
    ProductTable,
    SubscriptionTable,
    WorkflowTable,
    db,
)
from orchestrator.schemas.search import (
    ConnectionSchema,
    PageInfoSchema,
    PathsResponse,
    ProcessSearchSchema,
    ProductSearchSchema,
    SubscriptionSearchResult,
    WorkflowSearchSchema,
)
from orchestrator.schemas.subscription import SubscriptionDomainModelSchema
from orchestrator.search.core.types import EntityType, FieldType, UIType
from orchestrator.search.filters.definitions import generate_definitions
from orchestrator.search.retrieval import execute_search
from orchestrator.search.retrieval.builder import build_paths_query, create_path_autocomplete_lquery
from orchestrator.search.retrieval.validation import is_lquery_syntactically_valid
from orchestrator.search.schemas.parameters import (
    BaseSearchParameters,
    ProcessSearchParameters,
    ProductSearchParameters,
    SubscriptionSearchParameters,
    WorkflowSearchParameters,
)
from orchestrator.search.schemas.results import PathInfo, TypeDefinition

router = APIRouter()
T = TypeVar("T", bound=BaseModel)


async def _perform_search_and_fetch_simple(
    search_params: BaseSearchParameters,
    db_model: Any,
    response_schema: type[BaseModel],
    pk_column_name: str,
    eager_loads: list[Any],
) -> ConnectionSchema:
    results = await execute_search(search_params=search_params, db_session=db.session, limit=20)

    if not results:
        data: dict[str, Any] = {"page_info": PageInfoSchema(), "page": []}
        return ConnectionSchema(**cast(Any, data))

    entity_ids = [res.entity_id for res in results]
    pk_column = getattr(db_model, pk_column_name)
    ordering_case = case({entity_id: i for i, entity_id in enumerate(entity_ids)}, value=pk_column)

    stmt = select(db_model).options(*eager_loads).filter(pk_column.in_(entity_ids)).order_by(ordering_case)
    entities = db.session.scalars(stmt).all()

    page = [response_schema.model_validate(entity) for entity in entities]

    data = {"page_info": PageInfoSchema(), "page": page}
    return ConnectionSchema(**cast(Any, data))


@router.post(
    "/subscriptions",
    response_model=ConnectionSchema[SubscriptionSearchResult],
    response_model_by_alias=True,
)
async def search_subscriptions(
    search_params: SubscriptionSearchParameters,
) -> ConnectionSchema[SubscriptionSearchResult]:
    search_results = await execute_search(search_params=search_params, db_session=db.session, limit=20)

    if not search_results:
        data = {"page_info": PageInfoSchema(), "page": []}
        return ConnectionSchema(**cast(Any, data))

    search_info_map = {res.entity_id: res for res in search_results}
    entity_ids = list(search_info_map.keys())

    pk_column = SubscriptionTable.subscription_id
    ordering_case = case({entity_id: i for i, entity_id in enumerate(entity_ids)}, value=pk_column)

    stmt = (
        select(SubscriptionTable)
        .options(
            selectinload(SubscriptionTable.product),
            selectinload(SubscriptionTable.customer_descriptions),
        )
        .filter(pk_column.in_(entity_ids))
        .order_by(ordering_case)
    )
    subscriptions = db.session.scalars(stmt).all()

    page = []
    for sub in subscriptions:
        search_data = search_info_map.get(str(sub.subscription_id))
        if search_data:
            subscription_model = SubscriptionDomainModelSchema.model_validate(sub)

            result_item = SubscriptionSearchResult(
                score=search_data.score,
                highlight=search_data.highlight,
                subscription=subscription_model.model_dump(),
            )
            page.append(result_item)

    data = {"page_info": PageInfoSchema(), "page": page}
    return ConnectionSchema(**cast(Any, data))


@router.post("/workflows", response_model=ConnectionSchema[WorkflowSearchSchema], response_model_by_alias=True)
async def search_workflows(search_params: WorkflowSearchParameters) -> ConnectionSchema[WorkflowSearchSchema]:
    return await _perform_search_and_fetch_simple(
        search_params=search_params,
        db_model=WorkflowTable,
        response_schema=WorkflowSearchSchema,
        pk_column_name="workflow_id",
        eager_loads=[selectinload(WorkflowTable.products)],
    )


@router.post("/products", response_model=ConnectionSchema[ProductSearchSchema], response_model_by_alias=True)
async def search_products(search_params: ProductSearchParameters) -> ConnectionSchema[ProductSearchSchema]:
    return await _perform_search_and_fetch_simple(
        search_params=search_params,
        db_model=ProductTable,
        response_schema=ProductSearchSchema,
        pk_column_name="product_id",
        eager_loads=[
            selectinload(ProductTable.workflows),
            selectinload(ProductTable.fixed_inputs),
            selectinload(ProductTable.product_blocks),
        ],
    )


@router.post("/processes", response_model=ConnectionSchema[ProcessSearchSchema], response_model_by_alias=True)
async def search_processes(search_params: ProcessSearchParameters) -> ConnectionSchema[ProcessSearchSchema]:
    return await _perform_search_and_fetch_simple(
        search_params=search_params,
        db_model=ProcessTable,
        response_schema=ProcessSearchSchema,
        pk_column_name="process_id",
        eager_loads=[
            selectinload(ProcessTable.workflow),
        ],
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

    paths = [
        PathInfo(
            path=str(path),
            type=UIType.from_field_type(FieldType(value_type)),
        )
        for path, value_type in rows
    ]

    return PathsResponse(prefix=prefix, paths=paths)


@router.get(
    "/definitions",
    response_model=dict[UIType, TypeDefinition],
    response_model_exclude_none=True,
)
async def get_definitions() -> dict[UIType, TypeDefinition]:
    """Provide a static definition of operators and schemas for each UI type."""
    return generate_definitions()
