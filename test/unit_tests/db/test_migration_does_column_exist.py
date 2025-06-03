from orchestrator.db import db
from orchestrator.migrations.helpers import has_table_column


def test_select_from_table():
    # Testing if Table Workflows exist with column is_task
    # it should because the db.session depends on the session where all migrations are already run
    session = db.session
    result = has_table_column(table_name="workflows", column_name="is_task", conn=session)
    assert result is True, "Column 'is_task' does not exist in 'workflows' table"
