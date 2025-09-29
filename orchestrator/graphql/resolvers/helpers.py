from collections.abc import Sequence

import structlog
from sqlalchemy import CompoundSelect, Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.strategy_options import _AbstractLoad

from orchestrator.db import async_db
from orchestrator.db.database import BaseModel

logger = structlog.get_logger(__name__)


async def rows_from_statement(
    stmt: Select | CompoundSelect,
    base_table: type[BaseModel],
    session: AsyncSession | None = None,
    unique: bool = False,
    loaders: Sequence[_AbstractLoad] = (),
) -> Sequence:
    """Helper function to handle some tricky cases with sqlalchemy types."""
    # Tell SQLAlchemy that the rows must be objects of type `base_table` for CompoundSelect
    from_stmt = select(base_table).options(*loaders).from_statement(stmt)
    if session is None:
        logger.debug("### USING DEFAULT SESSION")
        async with async_db.session() as session:
            result = await session.scalars(from_stmt)
    else:
        logger.debug("### USING USER-PROVIDED SESSION")
        result = await session.scalars(from_stmt)
    uresult = result.unique() if unique else result
    return uresult.all()
