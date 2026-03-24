from unittest.mock import MagicMock, patch

from orchestrator.workflow import PredicateContext, RunPredicateFail, RunPredicatePass
from orchestrator.workflows.predicates import no_uncompleted_instance


class TestNoUncompletedInstance:
    @patch("orchestrator.workflows.predicates.db")
    def test_pass_when_zero(self, mock_db):
        mock_db.session.scalar.return_value = 0
        context = MagicMock(spec=PredicateContext)
        context.workflow_key = "test_workflow"

        result = no_uncompleted_instance(context)

        assert isinstance(result, RunPredicatePass)

    @patch("orchestrator.workflows.predicates.db")
    def test_fail_when_nonzero(self, mock_db):
        mock_db.session.scalar.return_value = 3
        context = MagicMock(spec=PredicateContext)
        context.workflow_key = "test_workflow"

        result = no_uncompleted_instance(context)

        assert isinstance(result, RunPredicateFail)
        assert "test_workflow" in result.message
        assert "3" in result.message
