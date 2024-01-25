from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import CompilerElement


def to_sql_string(stmt: CompilerElement) -> str:
    dialect = postgresql.dialect()  # type: ignore
    return str(stmt.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
