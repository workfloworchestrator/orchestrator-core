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

from unittest import mock
from uuid import uuid4

import pytest

from orchestrator.core.workflow_designer import source
from orchestrator.core.workflow_designer.source import DesignedWorkflowSource
from orchestrator.core.workflows import WORKFLOW_SOURCES, get_workflow

DEFINITION = {
    "name": "designed_note",
    "description": "Set a value",
    "form_fields": [],
    "steps": [{"step_id": "designer:set_value", "config": {"key": "checked_by", "value": "x"}}],
}


@pytest.fixture
def designed():
    return DesignedWorkflowSource()


@pytest.fixture
def db_configured(monkeypatch):
    monkeypatch.setattr(source, "_db_configured", lambda: True)


def test_designer_source_is_registered_by_default():
    assert source.designed_workflows in WORKFLOW_SOURCES


def test_names_without_prefix_never_reach_the_database(designed, db_configured):
    with mock.patch.object(source, "_fetch_definition") as fetch:
        assert designed.get("modify_note") is None
    fetch.assert_not_called()


def test_without_a_database_nothing_is_designed(designed, monkeypatch):
    monkeypatch.setattr(source, "_db_configured", lambda: False)
    with mock.patch.object(source, "_fetch_definition") as fetch:
        assert designed.get("designed_note") is None
        assert designed.names() == set()
    fetch.assert_not_called()


def test_get_workflow_falls_back_to_designed_workflows(db_configured):
    with mock.patch.object(source, "_fetch_definition", return_value=(uuid4(), 1, DEFINITION)):
        workflow = get_workflow("designed_note")
    source.designed_workflows.invalidate()

    assert workflow is not None
    assert [step.name for step in workflow.steps] == ["Start", "Set checked_by", "Done"]


def test_built_workflow_is_cached_until_version_or_row_changes(designed, db_configured):
    workflow_id = uuid4()
    rows = iter(
        [
            (workflow_id, 1, DEFINITION),
            (workflow_id, 1, DEFINITION),
            (workflow_id, 2, DEFINITION),
            (uuid4(), 2, DEFINITION),
        ]
    )

    with mock.patch.object(source, "_fetch_definition", side_effect=lambda name: next(rows)):
        first = designed.get("designed_note")
        same = designed.get("designed_note")
        new_version = designed.get("designed_note")
        recreated = designed.get("designed_note")

    assert first is same
    assert new_version is not same
    assert recreated is not new_version


def test_deleted_definition_is_forgotten(designed, db_configured):
    with mock.patch.object(source, "_fetch_definition", side_effect=[(uuid4(), 1, DEFINITION), None]):
        assert designed.get("designed_note") is not None
        assert designed.get("designed_note") is None
    assert designed._cache == {}


def test_invalid_stored_definition_becomes_a_placeholder_workflow(designed, db_configured):
    with mock.patch.object(source, "_fetch_definition", return_value=(uuid4(), 1, {"name": "?"})):
        workflow = designed.get("designed_broken")

    assert workflow is not None
    assert workflow.name == "designed_broken"
    assert [step.name for step in workflow.steps] == ["Start", "Unavailable step designed_broken", "Done"]


def test_invalidate(designed):
    designed._cache.update({"designed_a": ((uuid4(), 1), None), "designed_b": ((uuid4(), 1), None)})

    designed.invalidate("designed_a")
    assert set(designed._cache) == {"designed_b"}
    designed.invalidate()
    assert designed._cache == {}
