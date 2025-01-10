# Copyright 2019-2020 SURF.
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


from more_itertools import first

from orchestrator.db import ProcessStepTable, ProcessTable, SubscriptionTable
from orchestrator.utils.get_updated_properties import get_dict_updates
from orchestrator.workflow import ProcessStat, Step, StepStatus
from pydantic_forms.core import generate_form


def format_subscription(subscription: SubscriptionTable) -> dict:
    prod = subscription.product

    return {
        "subscription_id": subscription.subscription_id,
        "customer_id": subscription.customer_id,
        "product_id": prod.product_id,
        "description": subscription.description,
        "insync": subscription.insync,
        "status": subscription.status,
        "note": subscription.note,
        "start_date": subscription.start_date if subscription.start_date else None,
        "end_date": subscription.end_date if subscription.end_date else None,
        "version": subscription.version,
        "product": {
            "product_id": prod.product_id,
            "description": prod.description,
            "name": prod.name,
            "tag": prod.tag,
            "status": prod.status,
            "product_type": prod.product_type,
        },
    }


step_finish_statuses = [StepStatus.SUCCESS, StepStatus.SKIPPED, StepStatus.COMPLETE]


def find_previous_step(steps: list[ProcessStepTable], index: int) -> ProcessStepTable | None:
    return first([step for step in reversed(steps[:index]) if step.status in step_finish_statuses], None)


def enrich_step_details(step: ProcessStepTable, previous_step: ProcessStepTable | None) -> dict:
    state_delta = get_dict_updates(previous_step.state, step.state) if previous_step else step.state

    return {
        "name": step.name,
        "executed": step.executed_at.timestamp(),
        "status": step.status,
        "state": step.state,
        "created_by": step.created_by,
        "step_id": step.step_id,
        "stepid": step.step_id,
        "state_delta": state_delta,
    }


def enrich_process_details(process: ProcessTable, p_stat: ProcessStat) -> dict:
    current_state = p_stat.state.unwrap() if p_stat.state else None
    steps: list[ProcessStepTable] = process.steps
    dict_steps = [enrich_step_details(step, find_previous_step(steps, index)) for index, step in enumerate(steps)]

    def step_fn(step: Step) -> dict:
        return {"name": step.name, "status": "pending"}

    dict_steps += list(map(step_fn, p_stat.log)) if p_stat.log else []
    form = p_stat.log[0].form if p_stat.log else None
    generated_form = generate_form(form, current_state, []) if form and current_state else None

    return {
        "steps": dict_steps,
        "form": generated_form,
        "current_state": current_state,
    }


def enrich_process(process: ProcessTable, p_stat: ProcessStat | None = None) -> dict:
    # process.subscriptions is a non JSON serializable AssociationProxy
    # So we need to build a list of Subscriptions here.
    subscriptions = [format_subscription(sub) for sub in process.subscriptions]

    details = enrich_process_details(process, p_stat) if p_stat else {}

    return {
        "process_id": process.process_id,
        "product_id": subscriptions[0]["product"]["product_id"] if subscriptions else None,
        "customer_id": subscriptions[0]["customer_id"] if subscriptions else None,
        "assignee": process.assignee,
        "last_status": process.last_status,
        "last_step": process.last_step,
        "is_task": process.is_task,
        "workflow_id": process.workflow_id,
        "workflow_name": process.workflow.name,
        "workflow_target": process.process_subscriptions[0].workflow_target if process.process_subscriptions else None,
        "failed_reason": process.failed_reason,
        "created_by": process.created_by,
        "started_at": process.started_at,
        "traceback": process.traceback,
        "last_modified_at": process.last_modified_at,
        "product": subscriptions[0]["product"] if subscriptions else None,
        "subscriptions": subscriptions,
        "steps": None,
        "form": None,
        "current_state": None,
    } | details
