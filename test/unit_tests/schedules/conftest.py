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

from collections.abc import Iterator
from types import SimpleNamespace
from unittest import mock
from unittest.mock import Mock
from uuid import NAMESPACE_DNS, uuid5

import pytest


@pytest.fixture
def mock_add_schedule(request: pytest.FixtureRequest) -> Iterator[Mock]:
    """Patch the schedule queue, resolving only the workflow names passed as the indirect param."""
    workflow_map = {name: SimpleNamespace(workflow_id=uuid5(NAMESPACE_DNS, name)) for name in request.param}
    with (
        mock.patch(
            "orchestrator.core.schedules.service.get_workflow_by_name", side_effect=lambda name: workflow_map.get(name)
        ),
        mock.patch("orchestrator.core.schedules.service.add_unique_scheduled_task_to_queue") as mock_add,
    ):
        yield mock_add
