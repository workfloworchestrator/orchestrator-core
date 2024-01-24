from collections.abc import Sequence

from sqlalchemy import CompoundSelect, Select, select

from orchestrator.db import db
from orchestrator.db.database import BaseModel


def rows_from_statement(stmt: Select | CompoundSelect, base_table: type[BaseModel], unique: bool = False) -> Sequence:
    """Helper function to handle some tricky cases with sqlalchemy types."""
    # Tell SQLAlchemy that the rows must be objects of type `base_table`for CompoundSelect
    from_stmt = select(base_table).from_statement(stmt)
    result = db.session.scalars(from_stmt)
    uresult = result.unique() if unique else result
    return uresult.all()
