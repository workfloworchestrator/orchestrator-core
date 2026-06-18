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

from orchestrator.core.settings import app_settings


def get_workflow_guide(workflow_name: str) -> str | None:
    """Return the Markdown guide for a workflow, or None if not found."""
    if not app_settings.WORKFLOW_GUIDE_DIR:
        return None

    guide_file = app_settings.WORKFLOW_GUIDE_DIR / f"{workflow_name}.md"
    if not guide_file.exists():
        return None

    return guide_file.read_text(encoding="utf-8")
