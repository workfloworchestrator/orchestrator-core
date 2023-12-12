from typing import Optional, Iterable

from sqlalchemy import Select

from orchestrator.db import WorkflowTable, db
from orchestrator.schemas import WorkflowSchema, StepSchema
from orchestrator.workflows import get_workflow


def _add_steps_to_workflow(workflow: WorkflowTable) -> WorkflowSchema:
    def get_steps() -> list[StepSchema]:
        if registered_workflow := get_workflow(workflow.name):
            return [StepSchema(name=step.name) for step in registered_workflow.steps]
        raise AssertionError(f"Workflow {workflow.name} should be registered")

    return WorkflowSchema(
        workflow_id=workflow.workflow_id,
        name=workflow.name,
        target=workflow.target,
        description=workflow.description,
        created_at=workflow.created_at,
        steps=get_steps(),
    )


def get_workflows(filters: Optional[dict] = None, include_steps: bool = False) -> Iterable[WorkflowSchema]:
    def _add_filter(stmt: Select) -> Select:
        for k, v in (filters or {}).items():
            stmt = stmt.where(WorkflowTable.__dict__[k] == v)
        return stmt

    workflows = db.session.scalars(_add_filter(WorkflowTable.select())).all()

    if include_steps:
        workflows = [_add_steps_to_workflow(wf) for wf in workflows]

    return workflows
