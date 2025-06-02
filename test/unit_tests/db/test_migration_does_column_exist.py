from orchestrator.db import db
from sqlalchemy import text

from orchestrator.migrations.helpers import has_table_column

def test_select_from_table():
    # Since your fixture does not yield a session but manages scoped_session internally,
    # we access the session via your db.wrapped_database.scoped_session
    session = db.session
    result = has_table_column(table_name="workflows", column_name="is_task", conn=session)
    assert result is True, "Column 'is_task' does not exist in 'workflows' table"
