import pytest

from orchestrator.db import WorkflowTable, db
from orchestrator.targets import Target
from orchestrator.utils.datetime import nowtz


@pytest.fixture
def add_soft_deleted_workflows():
    def _add_soft_deleted_workflow(n: int):
        for i in range(n):
            db.session.add(
                WorkflowTable(
                    name=f"deleted_workflow_{i}",
                    description="deleted workflow",
                    target=Target.SYSTEM,
                    deleted_at=nowtz(),
                )
            )
        db.session.commit()

    return _add_soft_deleted_workflow
