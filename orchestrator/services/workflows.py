# Copyright 2019-2025 SURF.
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

from collections.abc import Iterable

from sqlalchemy import Select, select

from orchestrator.db import (
    SubscriptionTable,
    WorkflowTable,
    db,
)
from orchestrator.schemas import StepSchema, WorkflowSchema
from orchestrator.services.subscriptions import TARGET_DEFAULT_USABLE_MAP, WF_USABLE_MAP
from orchestrator.targets import Target
from orchestrator.workflows import get_workflow


def _get_steps(workflow: WorkflowTable) -> list[StepSchema]:
    if registered_workflow := get_workflow(workflow.name):
        return [StepSchema(name=step.name) for step in registered_workflow.steps]
    raise AssertionError(f"Workflow {workflow.name} should be registered")


def _to_workflow_schema(workflow: WorkflowTable, include_steps: bool = False) -> WorkflowSchema:
    extra_kwargs = {"steps": _get_steps(workflow)} if include_steps else {}

    return WorkflowSchema(
        workflow_id=workflow.workflow_id,
        name=workflow.name,
        target=workflow.target,
        is_task=workflow.is_task,
        description=workflow.description,
        created_at=workflow.created_at,
        **extra_kwargs,
    )


def get_workflows(
    filters: dict | None = None, include_steps: bool = False, include_deleted: bool = False
) -> Iterable[WorkflowSchema]:
    def _add_filter(stmt: Select) -> Select:
        for k, v in (filters or {}).items():
            stmt = stmt.where(WorkflowTable.__dict__[k] == v)
        return stmt

    stmt = select(WorkflowTable) if include_deleted else WorkflowTable.select()
    workflows = db.session.scalars(_add_filter(stmt)).all()

    return [_to_workflow_schema(wf, include_steps=include_steps) for wf in workflows]


def get_workflow_by_name(workflow_name: str) -> WorkflowTable | None:
    return db.session.scalar(select(WorkflowTable).where(WorkflowTable.name == workflow_name))


def get_validation_product_workflows_for_subscription(
    subscription: SubscriptionTable,
) -> list:
    return [workflow.name for workflow in subscription.product.workflows if workflow.target == Target.VALIDATE]


def start_validation_workflow_for_workflows(
    subscription: SubscriptionTable,
    workflows: list,
    product_type_filter: str | None = None,
) -> list:
    """Start validation workflows for a subscription."""
    result = []

    for workflow_name in workflows:
        target_system = TARGET_DEFAULT_USABLE_MAP[Target.SYSTEM]
        system_usable_when = WF_USABLE_MAP.get(workflow_name, target_system)
        target_validate = TARGET_DEFAULT_USABLE_MAP[Target.VALIDATE]
        validate_usable_when = WF_USABLE_MAP.get(workflow_name, target_validate)

        usable_when = system_usable_when + validate_usable_when
        if subscription.status in usable_when and (
            product_type_filter is None or subscription.product.product_type == product_type_filter
        ):
            json = [{"subscription_id": str(subscription.subscription_id)}]

            # against circular import
            from orchestrator.services.processes import get_execution_context

            validate_func = get_execution_context()["validate"]
            validate_func(workflow_name, json=json)

            result.append(
                {
                    "workflow_name": workflow_name,
                    "subscription_id": subscription.subscription_id,
                    "product_type": subscription.product.product_type,
                }
            )

    return result
