from collections.abc import Sequence
from functools import wraps
from typing import Callable, Coroutine

import structlog
from sqlalchemy import CompoundSelect, Select, select
from sqlalchemy.orm.strategy_options import _AbstractLoad
from starlette.concurrency import run_in_threadpool

from orchestrator.db import db
from orchestrator.db.database import BaseModel

logger = structlog.get_logger(__name__)


def rows_from_statement(
    stmt: Select | CompoundSelect,
    base_table: type[BaseModel],
    unique: bool = False,
    loaders: Sequence[_AbstractLoad] = (),
) -> Sequence:
    """Helper function to handle some tricky cases with sqlalchemy types."""
    # Tell SQLAlchemy that the rows must be objects of type `base_table` for CompoundSelect
    from_stmt = select(base_table).options(*loaders).from_statement(stmt)
    result = db.session.scalars(from_stmt)
    uresult = result.unique() if unique else result
    return uresult.all()


def make_async(f: Callable):  # type: ignore
    @wraps(f)
    async def wrapper(*args, **kwargs) -> Coroutine:  # type: ignore
        logger.debug(f"**async, calling fn {f.__name__}")
        return await run_in_threadpool(f, *args, **kwargs)

    return wrapper
