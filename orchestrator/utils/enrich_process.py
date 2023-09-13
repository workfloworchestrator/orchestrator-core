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

from typing import Optional

from orchestrator.db import ProcessTable, SubscriptionTable
from orchestrator.workflow import ProcessStat, Step
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
        "product": {
            "product_id": prod.product_id,
            "description": prod.description,
            "name": prod.name,
            "tag": prod.tag,
            "status": prod.status,
            "product_type": prod.product_type,
        },
    }


def enrich_process_details(process: ProcessTable, p_stat: ProcessStat) -> dict:
    current_state = p_stat.state.unwrap() if p_stat.state else None

    steps = [
        {
            "name": step.name,
            "executed": step.executed_at.timestamp(),
            "status": step.status,
            "state": step.state,
            "created_by": step.created_by,
            "step_id": step.step_id,
            "stepid": step.step_id,
        }
        for step in process.steps
    ]

    def step_fn(step: Step) -> dict:
        return {"name": step.name, "status": "pending"}

    steps += list(map(step_fn, p_stat.log)) if p_stat.log else []
    form = p_stat.log[0].form if p_stat.log else None
    generated_form = generate_form(form, current_state, []) if form and current_state else None

    return {
        "steps": steps,
        "form": generated_form,
        "current_state": current_state,
    }


def enrich_process(process: ProcessTable, p_stat: Optional[ProcessStat] = None) -> dict:
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
        "workflow_name": process.workflow_name,
        "workflow_target": process.process_subscriptions[0].workflow_target if process.process_subscriptions else None,
        "failed_reason": process.failed_reason,
        "created_by": process.created_by,
        "started_at": process.started_at,
        "last_modified_at": process.last_modified_at,
        "product": subscriptions[0]["product"] if subscriptions else None,
        "subscriptions": subscriptions,
        "steps": None,
        "form": None,
        "current_state": None,
        "id": process.process_id,  # TODO: will be removed in 1.4
        "pid": process.process_id,  # TODO: will be removed in 1.4
        "workflow": process.workflow_name,  # TODO: will be removed in 1.4
        "status": process.last_status,  # TODO: will be removed in 1.4
        "step": process.last_step,  # TODO: will be removed in 1.4
        "started": process.started_at,  # TODO: will be removed in 1.4
        "last_modified": process.last_modified_at,  # TODO: will be removed in 1.4
        "customer": subscriptions[0]["customer_id"] if subscriptions else None,  # TODO: will be removed in 1.4
    } | details
