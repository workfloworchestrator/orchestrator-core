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

from orchestrator.db import ProcessTable
from orchestrator.forms import generate_form
from orchestrator.workflow import ProcessStat


def show_process(process: ProcessTable, pStat: ProcessStat) -> dict:
    subscription = first(process.subscriptions, None)
    if subscription:
        product_id = subscription.product_id
        customer_id = subscription.customer_id
    else:
        product_id = None
        customer_id = None

    steps = [
        {
            "name": step.name,
            "executed": step.executed_at.timestamp(),
            "status": step.status,
            "state": step.state,
            "created_by": step.created_by,
            "stepid": step.stepid,
        }
        for step in process.steps
    ]

    form = None
    if pStat.log:
        form = pStat.log[0].form
        pstat_steps = list(map(lambda step: {"name": step.name, "status": "pending"}, pStat.log))
        steps += pstat_steps

    current_state = pStat.state.unwrap() if pStat.state else None
    generated_form = generate_form(form, current_state, []) if form and current_state else None

    return {
        "id": process.pid,
        "pid": process.pid,  # list and single get differentiate with this value and the above.
        "workflow": process.workflow,
        "workflow_name": process.workflow,
        "product": product_id,
        "customer": customer_id,
        "assignee": process.assignee,
        "status": process.last_status,
        "last_status": process.last_status,  # list and single get differentiate with this value and the above.
        "failed_reason": process.failed_reason,
        "traceback": process.traceback,
        "step": process.last_step,
        "steps": steps,
        "created_by": process.created_by,
        "started": process.started_at.timestamp(),
        "last_modified": process.last_modified_at.timestamp(),
        "subscriptions": [
            # explicit conversion using excluded_keys to prevent eager loaded subscriptions (when loaded for form domain models)
            # to cause circular reference errors
            s.subscription.__json__(excluded_keys={"instances", "customer_descriptions", "processes", "product"})
            for s in process.process_subscriptions
        ],
        "is_task": process.is_task,
        "form": generated_form,
        "current_state": current_state,
    }
