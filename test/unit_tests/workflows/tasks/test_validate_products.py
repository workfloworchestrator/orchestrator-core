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

"""Unit tests for the workflow registration check of task_validate_products."""

from types import SimpleNamespace
from unittest import mock

import pytest

import orchestrator.core.workflows as workflows_module
import orchestrator.core.workflows.tasks.validate_products as validate_products
from orchestrator.core.utils.functional import orig


def _check(db_names: set[str], code_names: set[str], source_names: set[str]):
    source = SimpleNamespace(get=lambda name: None, names=lambda: source_names, owned_names=lambda: source_names)
    with (
        mock.patch.object(validate_products, "get_workflows", return_value=[SimpleNamespace(name=n) for n in db_names]),
        mock.patch.object(workflows_module, "ALL_WORKFLOWS", dict.fromkeys(code_names)),
        mock.patch.object(workflows_module, "WORKFLOW_SOURCES", [source]),
    ):
        return orig(validate_products.check_all_workflows_are_in_db)()


def test_check_all_workflows_are_in_db_accepts_workflows_from_sources():
    result = _check(
        db_names={"modify_note", "designed_task"}, code_names={"modify_note"}, source_names={"designed_task"}
    )

    assert result == {"check_all_workflows_are_in_db": True}


@pytest.mark.parametrize(
    ("db_names", "code_names", "missing_key", "missing"),
    [
        pytest.param(
            {"modify_note", "stale"},
            {"modify_note"},
            "Workflows not registered in a `LazyWorkflowInstance`",
            ["stale"],
            id="row-without-workflow",
        ),
        pytest.param(
            {"modify_note"},
            {"modify_note", "new"},
            "Workflows not registered in the database",
            ["new"],
            id="workflow-without-row",
        ),
    ],
)
def test_check_all_workflows_are_in_db_reports_mismatches(db_names, code_names, missing_key, missing):
    with pytest.raises(validate_products.ProcessFailureError) as error:
        _check(db_names=db_names, code_names=code_names, source_names=set())

    assert error.value.details[missing_key] == missing
