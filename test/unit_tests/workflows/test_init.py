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

"""Tests for LazyWorkflowInstance error handling and get_workflow lookup."""

import pytest

from orchestrator.core.workflows import ALL_WORKFLOWS, LazyWorkflowInstance, get_workflow


@pytest.fixture(autouse=True)
def _clean_all_workflows():
    """Snapshot and restore ALL_WORKFLOWS to prevent global state leaks."""
    original = ALL_WORKFLOWS.copy()
    yield
    ALL_WORKFLOWS.clear()
    ALL_WORKFLOWS.update(original)


@pytest.mark.parametrize(
    "module_path",
    [
        pytest.param(".nonexistent_module_xyz", id="relative"),
        pytest.param("fake.nonexistent.module.xyz", id="absolute"),
    ],
)
def test_lazy_workflow_instance_raises_on_missing_module(module_path: str) -> None:
    lwi = LazyWorkflowInstance(module_path, "some_fn")
    with pytest.raises(ValueError, match="does not exist or has invalid imports"):
        lwi.instantiate()


def test_lazy_workflow_instance_str_repr() -> None:
    lwi = LazyWorkflowInstance(".some_pkg", "some_fn")
    assert str(lwi) == ".some_pkg.some_fn"
    assert repr(lwi) == "LazyWorkflowInstance('.some_pkg','some_fn')"


def test_get_workflow_returns_none_for_unknown() -> None:
    assert get_workflow("nonexistent_workflow_xyz_12345") is None
