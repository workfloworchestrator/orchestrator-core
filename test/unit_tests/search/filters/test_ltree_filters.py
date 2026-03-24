"""Tests for orchestrator.search.filters.ltree_filters: LtreeFilter construction validation and to_expression operator dispatch."""

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

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.search.core.types import LTREE_SEPARATOR, FilterOp
from orchestrator.search.filters.ltree_filters import LtreeFilter

pytestmark = pytest.mark.search

_VALID_LTREE_OPS = [
    pytest.param(FilterOp.IS_DESCENDANT, id="is_descendant"),
    pytest.param(FilterOp.IS_ANCESTOR, id="is_ancestor"),
    pytest.param(FilterOp.MATCHES_LQUERY, id="matches_lquery"),
    pytest.param(FilterOp.PATH_MATCH, id="path_match"),
    pytest.param(FilterOp.HAS_COMPONENT, id="has_component"),
    pytest.param(FilterOp.NOT_HAS_COMPONENT, id="not_has_component"),
    pytest.param(FilterOp.ENDS_WITH, id="ends_with"),
]

_INVALID_LTREE_OPS = [
    pytest.param(FilterOp.EQ, id="eq"),
    pytest.param(FilterOp.NEQ, id="neq"),
    pytest.param(FilterOp.LT, id="lt"),
    pytest.param(FilterOp.LTE, id="lte"),
    pytest.param(FilterOp.GT, id="gt"),
    pytest.param(FilterOp.GTE, id="gte"),
    pytest.param(FilterOp.BETWEEN, id="between"),
    pytest.param(FilterOp.LIKE, id="like"),
]


# ---------------------------------------------------------------------------
# Model construction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("op", _VALID_LTREE_OPS)
def test_valid_ops_construct_successfully(op: FilterOp) -> None:
    f = LtreeFilter(op=op, value="some.path")  # type: ignore[arg-type]
    assert f.op == op
    assert f.value == "some.path"


@pytest.mark.parametrize("op", _INVALID_LTREE_OPS)
def test_invalid_ops_raise_validation_error(op: FilterOp) -> None:
    with pytest.raises(ValidationError):
        LtreeFilter(op=op, value="some.path")  # type: ignore[arg-type]


def test_value_field_stored() -> None:
    f = LtreeFilter(op=FilterOp.ENDS_WITH, value="leaf")
    assert f.value == "leaf"


# ---------------------------------------------------------------------------
# to_expression — individual operator branches
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "op, expected_sql_op, value, expected_arg_str",
    [
        pytest.param(FilterOp.IS_DESCENDANT, "<@", "root.child", "root.child", id="is_descendant"),
        pytest.param(FilterOp.IS_ANCESTOR, "@>", "root", "root", id="is_ancestor"),
    ],
)
def test_descendant_ancestor_calls_operator_with_ltree(
    op: FilterOp, expected_sql_op: str, value: str, expected_arg_str: str
) -> None:
    col = MagicMock()
    expected = MagicMock()
    col.op.return_value.return_value = expected

    f = LtreeFilter(op=op, value=value)  # type: ignore[arg-type]
    result = f.to_expression(col, "ignored")

    col.op.assert_called_once_with(expected_sql_op)
    call_arg = col.op.return_value.call_args[0][0]
    assert isinstance(call_arg, Ltree)
    assert str(call_arg) == expected_arg_str
    assert result is expected


def test_matches_lquery_calls_tilde_with_bindparam() -> None:
    col = MagicMock()
    expected = MagicMock()
    col.op.return_value.return_value = expected

    f = LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="*.child.*")
    result = f.to_expression(col, "ignored")

    col.op.assert_called_once_with("~")
    bound = col.op.return_value.call_args[0][0]
    assert bound.value == "*.child.*"
    assert result is expected


def test_path_match_uses_path_argument_not_value() -> None:
    col = MagicMock()
    expected = MagicMock()
    col.__eq__ = MagicMock(return_value=expected)  # type: ignore[method-assign]

    f = LtreeFilter(op=FilterOp.PATH_MATCH, value="filter.value")
    result = f.to_expression(col, "actual.path")

    col.__eq__.assert_called_once()
    ltree_arg = col.__eq__.call_args[0][0]
    assert isinstance(ltree_arg, Ltree)
    assert str(ltree_arg) == "actual.path"
    assert result is expected


@pytest.mark.parametrize(
    "op",
    [
        pytest.param(FilterOp.HAS_COMPONENT, id="has_component"),
        pytest.param(FilterOp.NOT_HAS_COMPONENT, id="not_has_component"),
    ],
)
def test_has_and_not_has_component_use_star_pattern(op: FilterOp) -> None:
    col = MagicMock()
    expected = MagicMock()
    col.op.return_value.return_value = expected

    f = LtreeFilter(op=op, value="segment")  # type: ignore[arg-type]
    result = f.to_expression(col, "ignored")

    col.op.assert_called_once_with("~")
    bound = col.op.return_value.call_args[0][0]
    assert bound.value == f"*{LTREE_SEPARATOR}segment{LTREE_SEPARATOR}*"
    assert result is expected


def test_ends_with_uses_star_prefix_pattern() -> None:
    col = MagicMock()
    expected = MagicMock()
    col.op.return_value.return_value = expected

    f = LtreeFilter(op=FilterOp.ENDS_WITH, value="leaf")
    result = f.to_expression(col, "ignored")

    col.op.assert_called_once_with("~")
    bound = col.op.return_value.call_args[0][0]
    assert bound.value == f"*{LTREE_SEPARATOR}leaf"
    assert result is expected
