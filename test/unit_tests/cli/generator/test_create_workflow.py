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

"""Tests for rendering the create workflow template."""

import pytest

from orchestrator.core.cli.generate import get_template_environment
from orchestrator.core.cli.generator.generator.workflow import render_template

_CONFIG = {
    "name": "Example",
    "type": "Example",
    "variable": "example",
    "config": {"summary_forms": False},
    "product_blocks": [
        {"name": "example", "type": "Example", "tag": "EXAMPLE", "fields": []},
    ],
}


@pytest.fixture
def rendered_create_workflow() -> str:
    return render_template(get_template_environment(), _CONFIG, "create_product.j2", "create")


def test_construct_model_accepts_process_id(rendered_create_workflow: str) -> None:
    """The create workflow must pass the process id so the ProcessSubscription relation is stored (#1879)."""
    assert "    process_id: UUIDstr,\n" in rendered_create_workflow
    assert "        process_id=process_id,\n" in rendered_create_workflow
