from typing import Union, Type, Sequence

from sqlalchemy import CompoundSelect, Select, select, func

from orchestrator.db import db
from orchestrator.db.database import BaseModel


def rows_total_from_statement(stmt: Union[Select, CompoundSelect], base_table: Type[BaseModel]) -> tuple[Sequence, int]:
    total = db.session.scalar(select(func.count()).select_from(stmt))
    # Tell SQLAlchemy that the rows must be objects of type `base_table`for CompoundSelect
    stmt = select(base_table).from_statement(stmt) if isinstance(stmt, CompoundSelect) else stmt
    return db.session.scalars(stmt).all(), total
