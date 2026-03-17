from decimal import Decimal
from typing import Any

import pytest
import strawberry

from orchestrator.graphql.types import SCALAR_OVERRIDES

BIG_INT_VALUE = 2**40  # 1,099,511,627,776
DECIMAL_VALUE = Decimal("1234567890.123456789")


@strawberry.type
class ScalarsTest:
    big_int: int
    decimal_value: Decimal


@strawberry.type
class Query:
    @strawberry.field
    def scalars(self) -> ScalarsTest:
        """Return test values for large int and decimal."""
        return ScalarsTest(big_int=BIG_INT_VALUE, decimal_value=DECIMAL_VALUE)


schema = strawberry.Schema(query=Query)
schema_with_overrides = strawberry.Schema(query=Query, scalar_overrides=SCALAR_OVERRIDES)


def test_big_int_and_decimal_handling() -> None:
    """Verify that large integers and Decimal values serialize correctly."""
    query = """
    query {
        scalars {
            bigInt
            decimalValue
        }
    }
    """

    result: Any = schema_with_overrides.execute_sync(query)
    assert result.errors is None, f"GraphQL errors occurred: {result.errors}"

    data = result.data["scalars"]

    assert data["bigInt"] == BIG_INT_VALUE
    decimal_serialized = str(data["decimalValue"])
    assert decimal_serialized.startswith(str(DECIMAL_VALUE))


@pytest.mark.xfail(reason="Graphql now supports non 32-bit signed integers", strict=False)
def test_big_int_and_decimal_handling_fails_without_scalar_overrides() -> None:
    """Verify that large integers and Decimal values serialize correctly."""
    query = """
    query {
        scalars {
            bigInt
            decimalValue
        }
    }
    """

    # with pytest.raises(GraphQLError, match="Int cannot represent non 32-bit signed integer"):
    result = schema.execute_sync(query)
    assert any("Int cannot represent non 32-bit signed integer" in err.message for err in result.errors or [])
