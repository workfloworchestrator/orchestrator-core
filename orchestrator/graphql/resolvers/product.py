import structlog
from strawberry.types import Info

from orchestrator.db.models import ProductTable
from orchestrator.graphql.resolvers.process import Cursor, ProcessSort
from orchestrator.graphql.schemas.product import Product

logger = structlog.get_logger(__name__)


async def resolve_products(
    info: Info,
    filter_by: list[tuple[str, str]] | None = None,
    sort_by: list[ProcessSort] | None = None,
    first: int = 10,
    after: Cursor = 0,
) -> list[Product]:
    # _range: list[int] | None = [after, after + first] if after is not None and first else None
    # _filter: list[str] | None = flatten(filter_by) if filter_by else None
    # logger.info("processes_filterable() called", range=_range, sort=sort_by, filter=_filter)

    results = ProductTable.query.all()

    return [Product.from_pydantic(p) for p in results]  # type: ignore
