from typing import Any, TypeVar, cast

from fastapi import APIRouter
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
    ProcessSearchSchema,
    ProductSearchSchema,
    SubscriptionSearchResult,
    WorkflowSearchSchema,
)
from orchestrator.schemas.subscription import SubscriptionDomainModelSchema
from orchestrator.search.retrieval import execute_search
from orchestrator.search.schemas.parameters import (
    BaseSearchParameters,
    ProcessSearchParameters,
    ProductSearchParameters,
    SubscriptionSearchParameters,
    WorkflowSearchParameters,
)

router = APIRouter(tags=["Search"], prefix="/search")
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
