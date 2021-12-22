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


def show_process(p: ProcessTable) -> dict:
    subscription = first(p.subscriptions, None)
    if subscription:
        product_id = subscription.product_id
        customer_id = subscription.customer_id
    else:
        product_id = None
        customer_id = None

    return {
        "id": p.pid,
        "workflow_name": p.workflow,
        "product": product_id,
        "customer": customer_id,
        "assignee": p.assignee,
        "status": p.last_status,
        "failed_reason": p.failed_reason,
        "traceback": p.traceback,
        "step": p.last_step,
        "created_by": p.created_by,
        "started": p.started_at,
        "last_modified": p.last_modified_at,
        "subscriptions": [
            # explicit conversion using excluded_keys to prevent eager loaded subscriptions (when loaded for form domain models)
            # to cause circular reference errors
            s.subscription.__json__(excluded_keys={"instances", "customer_descriptions", "processes", "product"})
            for s in p.process_subscriptions
        ],
        "is_task": p.is_task,
    }
