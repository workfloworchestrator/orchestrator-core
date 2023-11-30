from typing import Union, Type, Sequence

from sqlalchemy import CompoundSelect, Select, select, func

from orchestrator.db import db
from orchestrator.db.database import BaseModel


def rows_total_from_statement(
        stmt: Union[Select, CompoundSelect],
        base_table: Type[BaseModel],
        unique: bool = False) -> tuple[Sequence, int]:
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery()))
    # Tell SQLAlchemy that the rows must be objects of type `base_table`for CompoundSelect
    stmt = select(base_table).from_statement(stmt) if isinstance(stmt, CompoundSelect) else stmt
    result = db.session.scalars(stmt)
    result = result.unique() if unique else result
    return result.all(), total
