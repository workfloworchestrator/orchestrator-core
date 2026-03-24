"""Tests for no_uncompleted_instance predicate: pass on zero count, fail with message on nonzero."""

from unittest.mock import MagicMock, patch

import pytest

from orchestrator.workflow import PredicateContext, RunPredicateFail, RunPredicatePass
from orchestrator.workflows.predicates import no_uncompleted_instance


@pytest.mark.parametrize(
    "count,expected_type",
    [
        pytest.param(0, RunPredicatePass, id="zero-passes"),
        pytest.param(3, RunPredicateFail, id="nonzero-fails"),
    ],
)
@patch("orchestrator.workflows.predicates.db")
def test_no_uncompleted_instance(mock_db: MagicMock, count: int, expected_type: type) -> None:
    mock_db.session.scalar.return_value = count
    context = MagicMock(spec=PredicateContext)
    context.workflow_key = "test_workflow"
    result = no_uncompleted_instance(context)
    assert isinstance(result, expected_type)
