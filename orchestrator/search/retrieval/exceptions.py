# Copyright 2019-2025 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from orchestrator.search.core.types import FilterOp


class FilterValidationError(Exception):
    """Base exception for filter validation errors."""

    pass


class InvalidLtreePatternError(FilterValidationError):
    """Raised when an ltree pattern has invalid ltree query syntax."""

    def __init__(self, pattern: str) -> None:
        message = f"Ltree pattern '{pattern}' has invalid syntax. Use valid PostgreSQL ltree lquery syntax."
        super().__init__(message)


class EmptyFilterPathError(FilterValidationError):
    """Raised when a filter path is empty or contains only whitespace."""

    def __init__(self) -> None:
        message = (
            "Filter path cannot be empty. Provide a valid path like 'subscription.product.name' or 'workflow.name'."
        )
        super().__init__(message)


class PathNotFoundError(FilterValidationError):
    """Raised when a filter path doesn't exist in the database schema.

    Examples:
        Using a non-existent filter path:

        >>> print(PathNotFoundError('subscription.nonexistent.field'))
        Path 'subscription.nonexistent.field' does not exist in the database.
    """

    def __init__(self, path: str) -> None:
        message = f"Path '{path}' does not exist in the database."
        super().__init__(message)


class IncompatibleFilterTypeError(FilterValidationError):
    """Raised when a filter operator is incompatible with the field's data type.

    Examples:
        Using a numeric comparison operator on a string field:

        >>> print(IncompatibleFilterTypeError(
        ...     operator='gt',
        ...     field_type='string',
        ...     path='subscription.customer_name',
        ...     expected_operators=[FilterOp.EQ, FilterOp.NEQ, FilterOp.LIKE],
        ... ))
        Operator 'gt' is not compatible with field type 'string' for path 'subscription.customer_name'. Valid operators for 'string': [eq, neq, like]
    """

    def __init__(self, operator: str, field_type: str, path: str, expected_operators: list[FilterOp]) -> None:
        valid_ops_str = ", ".join([op.value for op in expected_operators])
        message = f"Operator '{operator}' is not compatible with field type '{field_type}' for path '{path}'. Valid operators for '{field_type}': [{valid_ops_str}]"

        super().__init__(message)


class InvalidEntityPrefixError(FilterValidationError):
    """Raised when a filter path doesn't have the correct entity type prefix.

    Examples:
        Using wrong entity prefix in filter path:

        >>> print(InvalidEntityPrefixError('workflow.name', 'subscription.', 'SUBSCRIPTION'))
        Filter path 'workflow.name' must start with 'subscription.' for SUBSCRIPTION searches, or use '*' for wildcard paths.
    """

    def __init__(self, path: str, expected_prefix: str, entity_type: str) -> None:
        message = f"Filter path '{path}' must start with '{expected_prefix}' for {entity_type} searches, or use '*' for wildcard paths."
        super().__init__(message)
