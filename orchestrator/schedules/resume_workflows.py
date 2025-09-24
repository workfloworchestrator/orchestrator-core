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


from orchestrator.schedules.scheduler import scheduler
from orchestrator.services.processes import start_process


@scheduler.scheduled_job(id="resume-workflows", name="Resume workflows", trigger="interval", hours=1)  # type: ignore[misc]
def run_resume_workflows() -> None:
    start_process("task_resume_workflows")
