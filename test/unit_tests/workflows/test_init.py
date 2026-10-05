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

from types import SimpleNamespace
from unittest import mock

import pytest

import orchestrator.core.workflows as workflows_module
from orchestrator.core.workflows import (
    ALL_WORKFLOWS,
    LazyWorkflowInstance,
    WorkflowSource,
    all_workflow_names,
    get_workflow,
    register_workflow_source,
    source_workflow_names,
)


@pytest.fixture(autouse=True)
def _clean_all_workflows():
    """Snapshot and restore ALL_WORKFLOWS to prevent global state leaks."""
    original = ALL_WORKFLOWS.copy()
    yield
    ALL_WORKFLOWS.clear()
    ALL_WORKFLOWS.update(original)


@pytest.fixture
def sources():
    """An empty, isolated list of workflow sources."""
    with mock.patch.object(workflows_module, "WORKFLOW_SOURCES", []) as patched:
        yield patched


class DictSource:
    def __init__(self, workflows: dict) -> None:
        self.workflows = workflows

    def get(self, name: str):
        return self.workflows.get(name)

    def names(self) -> set[str]:
        return set(self.workflows)


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


def test_dict_source_satisfies_protocol() -> None:
    assert isinstance(DictSource({}), WorkflowSource)


def test_get_workflow_falls_back_to_sources_in_order(sources) -> None:
    first_wf, second_wf = SimpleNamespace(name="first"), SimpleNamespace(name="second")
    register_workflow_source(DictSource({"only_first": first_wf, "both": first_wf}))
    register_workflow_source(DictSource({"both": second_wf, "only_second": second_wf}))

    assert get_workflow("only_first") is first_wf
    assert get_workflow("only_second") is second_wf
    assert get_workflow("both") is first_wf
    assert get_workflow("in_neither") is None


def test_get_workflow_prefers_code_over_sources(sources) -> None:
    code_wf = SimpleNamespace(name="code")
    lazy = LazyWorkflowInstance(".some_pkg", "shared_name")
    register_workflow_source(DictSource({"shared_name": SimpleNamespace(name="source")}))

    with mock.patch.object(lazy, "instantiate", return_value=code_wf):
        assert get_workflow("shared_name") is code_wf


def test_register_workflow_source_is_idempotent(sources) -> None:
    source = DictSource({})
    register_workflow_source(source)
    register_workflow_source(source)

    assert sources == [source]


def test_workflow_names(sources) -> None:
    register_workflow_source(DictSource({"designed_a": None}))
    register_workflow_source(DictSource({"designed_b": None}))

    assert source_workflow_names() == {"designed_a", "designed_b"}
    assert all_workflow_names() == set(ALL_WORKFLOWS) | {"designed_a", "designed_b"}
