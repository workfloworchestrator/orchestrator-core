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


from orchestrator.schedules.resume_workflows import run_resume_workflows
from orchestrator.schedules.scheduling import SchedulingFunction
from orchestrator.schedules.task_vacuum import vacuum_tasks
from orchestrator.schedules.validate_products import validate_products
from orchestrator.schedules.validate_subscriptions import validate_subscriptions

ALL_SCHEDULERS: list[SchedulingFunction] = [
    run_resume_workflows,
    vacuum_tasks,
    validate_subscriptions,
    validate_products,
]
