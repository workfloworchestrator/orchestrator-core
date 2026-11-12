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
from sqlalchemy.dialects import postgresql

from orchestrator.core.services.processes import _branch_child_step_ids_select, create_process
from orchestrator.core.targets import Target
from orchestrator.core.workflow import StepList, make_workflow, step


@pytest.mark.parametrize(
    "user_inputs,expected_post_form_inputs",
    [
        (None, [{}]),
        ([], []),
        ([{"a": 1}], [{"a": 1}]),
        ([{"a": 1}, {"b": 2}], [{"a": 1}, {"b": 2}]),
    ],
)
@mock.patch("orchestrator.core.services.processes.transactional")
@mock.patch("orchestrator.core.services.processes.store_input_state")
@mock.patch("orchestrator.core.services.processes._db_create_process")
@mock.patch("orchestrator.core.services.processes.post_form")
@mock.patch("orchestrator.core.services.processes.get_workflow")
def test_create_process_normalizes_user_inputs(
    mock_get_workflow,
    mock_post_form,
    mock_db_create_process,
    mock_store_input_state,
    mock_transactional,
    user_inputs,
    expected_post_form_inputs,
):
    @step("test step")
    def test_step():
        pass

    wf = make_workflow(lambda: None, "description", None, Target.SYSTEM, StepList([test_step]))
    wf.name = "wf_name"
    mock_get_workflow.return_value = wf
    mock_post_form.return_value = {}

    create_process("wf_name", user_inputs=user_inputs)

    mock_post_form.assert_called_once_with(wf.initial_input_form, mock.ANY, expected_post_form_inputs)


def test_branch_child_step_ids_select_is_scoped_to_the_process() -> None:
    """Pins the shape of the helper's SQL: the join and the process_id predicate.

    This covers the helper only. That the step write uses it is checked in
    ``test_parallel_workflow.py::test_step_updates_look_up_branch_children_scoped_to_the_process``.
    """
    process_id = uuid4()

    sql = str(
        _branch_child_step_ids_select(process_id).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )

    assert "JOIN process_steps ON process_step_relations.parent_step_id = process_steps.stepid" in sql
    assert f"process_steps.pid = '{process_id}'" in sql
