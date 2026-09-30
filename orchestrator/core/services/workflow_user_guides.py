# Copyright 2019-2026 SURF, GÉANT.
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

import os

from anyio import Path

from nwastdlib.file_utils import resolve_within_root_async
from orchestrator.core.settings import app_settings


async def get_workflow_guide(workflow_name: str | os.PathLike[str]) -> str | None:
    """Return the Markdown guide for a workflow, or None if not found.

    The guide file is resolved inside ``WORKFLOW_USER_GUIDE_DIR``; this function does not assume that
    ``workflow_name`` has already been validated. File IO is performed via ``anyio.Path`` so the event loop is
    never blocked.

    Raises:
        PathOutsideRootError: If ``workflow_name`` resolves to a path outside of ``WORKFLOW_USER_GUIDE_DIR``.
    """
    if app_settings.WORKFLOW_USER_GUIDE_DIR is None:
        return None

    guide_file = Path(await resolve_within_root_async(app_settings.WORKFLOW_USER_GUIDE_DIR, f"{workflow_name}.md"))
    if not await guide_file.is_file():
        return None

    return await guide_file.read_text(encoding="utf-8")
