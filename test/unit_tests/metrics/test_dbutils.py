import pytest
from psycopg import errors as psycopg_errors
from sqlalchemy.exc import ProgrammingError

from orchestrator.metrics.dbutils import handle_missing_tables


def test_handle_missing_tables_passes_through_normally() -> None:
    """No exception inside the block: context manager exits cleanly."""
    result = []
    with handle_missing_tables():
        result.append("executed")
    assert result == ["executed"]


def test_handle_missing_tables_suppresses_undefined_table_error() -> None:
    """ProgrammingError wrapping UndefinedTable is caught and not re-raised."""
    orig = psycopg_errors.UndefinedTable.__new__(psycopg_errors.UndefinedTable)
    exc = ProgrammingError("", {}, orig)

    with handle_missing_tables():
        raise exc  # must not propagate


@pytest.mark.parametrize(
    "orig",
    [
        pytest.param(Exception("other error"), id="generic-exception"),
        pytest.param(ValueError("bad value"), id="value-error"),
    ],
)
def test_handle_missing_tables_reraises_other_programming_errors(orig: Exception) -> None:
    """ProgrammingError wrapping anything other than UndefinedTable is re-raised."""
    exc = ProgrammingError("", {}, orig)

    with pytest.raises(ProgrammingError) as exc_info:
        with handle_missing_tables():
            raise exc

    assert exc_info.value is exc
