# Copyright 2019-2026 ESnet, GÉANT, SURF.
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

from pathlib import Path
from typing import Union

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from orchestrator.core.types import WORKFLOW_NAME_PATTERN, WorkflowName, is_of_type

workflow_name_adapter = TypeAdapter(WorkflowName)


def test_is_of_type():
    """Some tests to see type checks are valid."""
    assert is_of_type(int, Union[int, str])
    assert is_of_type(int, Union[str, int])
    assert is_of_type(str, Union[int, str])
    assert is_of_type(str, Union[str, int])
    assert is_of_type(list[str], Union[str, int]) is False


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("a", id="single-letter"),
        pytest.param("create_network", id="snake-case"),
        pytest.param("modify_node_v2", id="with-digits"),
        pytest.param("task_clean_up_", id="trailing-underscore"),
    ],
)
def test_workflow_name_accepts_valid_names(name: str) -> None:
    assert workflow_name_adapter.validate_python(name) == Path(name)


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("", id="empty"),
        pytest.param("CreateNetwork", id="uppercase"),
        pytest.param("1_workflow", id="leading-digit"),
        pytest.param("_workflow", id="leading-underscore"),
        pytest.param("create-network", id="hyphen"),
        pytest.param("create network", id="space"),
        pytest.param("create_network.md", id="extension"),
        pytest.param("..", id="parent-directory"),
        pytest.param("../etc/passwd", id="parent-traversal"),
        pytest.param("..%2fetc%2fpasswd", id="url-encoded-traversal"),
        pytest.param("/etc/passwd", id="absolute-path"),
        pytest.param("nested/workflow", id="subdirectory"),
        pytest.param("..\\windows", id="backslash"),
        pytest.param("workflow\n", id="trailing-newline"),
        pytest.param("workflow\x00", id="null-byte"),
        pytest.param("workflow;id", id="semicolon"),
        pytest.param("$(id)", id="command-substitution"),
        pytest.param("~root", id="tilde"),
        pytest.param("caf\u00e9", id="non-ascii"),
    ],
)
def test_workflow_name_rejects_invalid_names(name: str) -> None:
    with pytest.raises(ValidationError):
        workflow_name_adapter.validate_python(name)


@pytest.mark.parametrize(
    ("name", "message"),
    [
        pytest.param("workflow;id", "contains characters that are not allowed", id="rejected-by-safe-name"),
        pytest.param("CreateNetwork", "must be snake_case", id="rejected-by-snake-case"),
        pytest.param("../etc/passwd", "must be snake_case", id="traversal-rejected-by-snake-case"),
    ],
)
def test_workflow_name_error_message(name: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        workflow_name_adapter.validate_python(name)


def test_workflow_name_pattern_is_published_in_json_schema() -> None:
    class Model(BaseModel):
        name: WorkflowName

    assert Model.model_json_schema()["properties"]["name"]["pattern"] == WORKFLOW_NAME_PATTERN.pattern
