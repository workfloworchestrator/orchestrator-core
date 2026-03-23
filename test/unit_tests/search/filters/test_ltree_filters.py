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


# ---------------------------------------------------------------------------
# Model construction
# ---------------------------------------------------------------------------


class TestLtreeFilterConstruction:
    @pytest.mark.parametrize(
        "op",
        [
            FilterOp.IS_DESCENDANT,
            FilterOp.IS_ANCESTOR,
            FilterOp.MATCHES_LQUERY,
            FilterOp.PATH_MATCH,
            FilterOp.HAS_COMPONENT,
            FilterOp.NOT_HAS_COMPONENT,
            FilterOp.ENDS_WITH,
        ],
        ids=[
            "is_descendant",
            "is_ancestor",
            "matches_lquery",
            "path_match",
            "has_component",
            "not_has_component",
            "ends_with",
        ],
    )
    def test_valid_ops_construct_successfully(self, op: FilterOp) -> None:
        f = LtreeFilter(op=op, value="some.path")  # type: ignore[arg-type]
        assert f.op == op
        assert f.value == "some.path"

    @pytest.mark.parametrize(
        "op",
        [
            FilterOp.EQ,
            FilterOp.NEQ,
            FilterOp.LT,
            FilterOp.LTE,
            FilterOp.GT,
            FilterOp.GTE,
            FilterOp.BETWEEN,
            FilterOp.LIKE,
        ],
        ids=["eq", "neq", "lt", "lte", "gt", "gte", "between", "like"],
    )
    def test_invalid_ops_raise_validation_error(self, op: FilterOp) -> None:
        with pytest.raises(ValidationError):
            LtreeFilter(op=op, value="some.path")  # type: ignore[arg-type]

    def test_value_field_stored(self) -> None:
        f = LtreeFilter(op=FilterOp.ENDS_WITH, value="leaf")
        assert f.value == "leaf"


# ---------------------------------------------------------------------------
# to_expression — individual operator branches
# ---------------------------------------------------------------------------


class TestLtreeFilterToExpression:
    def test_is_descendant_calls_operator_with_ltree(self) -> None:
        col = MagicMock()
        expected = MagicMock()
        col.op.return_value.return_value = expected

        f = LtreeFilter(op=FilterOp.IS_DESCENDANT, value="root.child")
        result = f.to_expression(col, "ignored")

        col.op.assert_called_once_with("<@")
        call_arg = col.op.return_value.call_args[0][0]
        assert isinstance(call_arg, Ltree)
        assert str(call_arg) == "root.child"
        assert result is expected

    def test_is_ancestor_calls_operator_with_ltree(self) -> None:
        col = MagicMock()
        expected = MagicMock()
        col.op.return_value.return_value = expected

        f = LtreeFilter(op=FilterOp.IS_ANCESTOR, value="root")
        result = f.to_expression(col, "ignored")

        col.op.assert_called_once_with("@>")
        call_arg = col.op.return_value.call_args[0][0]
        assert isinstance(call_arg, Ltree)
        assert str(call_arg) == "root"
        assert result is expected

    def test_matches_lquery_calls_tilde_with_bindparam(self) -> None:
        col = MagicMock()
        expected = MagicMock()
        col.op.return_value.return_value = expected

        f = LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="*.child.*")
        result = f.to_expression(col, "ignored")

        col.op.assert_called_once_with("~")
        # The argument is a bindparam — check its value
        bound = col.op.return_value.call_args[0][0]
        assert bound.value == "*.child.*"
        assert result is expected

    def test_path_match_uses_path_argument_not_value(self) -> None:
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
        [FilterOp.HAS_COMPONENT, FilterOp.NOT_HAS_COMPONENT],
        ids=["has_component", "not_has_component"],
    )
    def test_has_and_not_has_component_use_star_pattern(self, op: FilterOp) -> None:
        col = MagicMock()
        expected = MagicMock()
        col.op.return_value.return_value = expected

        f = LtreeFilter(op=op, value="segment")  # type: ignore[arg-type]
        result = f.to_expression(col, "ignored")

        col.op.assert_called_once_with("~")
        bound = col.op.return_value.call_args[0][0]
        assert bound.value == f"*{LTREE_SEPARATOR}segment{LTREE_SEPARATOR}*"
        assert result is expected

    def test_ends_with_uses_star_prefix_pattern(self) -> None:
        col = MagicMock()
        expected = MagicMock()
        col.op.return_value.return_value = expected

        f = LtreeFilter(op=FilterOp.ENDS_WITH, value="leaf")
        result = f.to_expression(col, "ignored")

        col.op.assert_called_once_with("~")
        bound = col.op.return_value.call_args[0][0]
        assert bound.value == f"*{LTREE_SEPARATOR}leaf"
        assert result is expected

    @pytest.mark.parametrize(
        "op, value, path",
        [
            (FilterOp.IS_DESCENDANT, "a.b", "ignored"),
            (FilterOp.IS_ANCESTOR, "a", "ignored"),
            (FilterOp.MATCHES_LQUERY, "*.b.*", "ignored"),
            (FilterOp.HAS_COMPONENT, "comp", "ignored"),
            (FilterOp.NOT_HAS_COMPONENT, "comp", "ignored"),
            (FilterOp.ENDS_WITH, "tail", "ignored"),
        ],
        ids=["is_descendant", "is_ancestor", "matches_lquery", "has_component", "not_has_component", "ends_with"],
    )
    def test_to_expression_returns_value(self, op: FilterOp, value: str, path: str) -> None:
        col = MagicMock()
        f = LtreeFilter(op=op, value=value)  # type: ignore[arg-type]
        result = f.to_expression(col, path)
        assert result is not None
