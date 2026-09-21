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

from collections.abc import Callable, Iterator
from types import SimpleNamespace
from unittest import mock
from unittest.mock import Mock
from uuid import NAMESPACE_DNS, uuid5

import pytest


@pytest.fixture
def mock_schedule_queue() -> Iterator[Callable[..., Mock]]:
    """Patch the schedule queue, yielding a callable that declares which workflow names resolve.

    Call it with the known workflow names; it returns the patched
    `add_unique_scheduled_task_to_queue` mock. Any other name resolves to None.
    """
    workflow_map: dict[str, SimpleNamespace] = {}
    with (
        mock.patch(
            "orchestrator.core.schedules.service.get_workflow_by_name", side_effect=lambda name: workflow_map.get(name)
        ),
        mock.patch("orchestrator.core.schedules.service.add_unique_scheduled_task_to_queue") as mock_add,
    ):

        def known_workflows(*names: str) -> Mock:
            workflow_map.update({name: SimpleNamespace(workflow_id=uuid5(NAMESPACE_DNS, name)) for name in names})
            return mock_add

        yield known_workflows
