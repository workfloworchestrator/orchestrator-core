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
import pytest
from pydantic import ValidationError

from orchestrator.core.workflow_designer.definition import StepRef, WorkflowDefinition, validate_definition
from orchestrator.core.workflow_designer.discovery import StepInfo, StepInput
from orchestrator.core.workflow_designer.forms import FormField
from orchestrator.core.workflow_designer.inference import StateKey
from orchestrator.core.workflow_designer.type_refs import TypeRef

STEPS = {
    "m:load_zone": StepInfo(
        id="m:load_zone",
        name="Load zone",
        function="load_zone",
        module="m",
        category="m",
        kind="step",
        inputs=[StepInput(name="customer_name", type=TypeRef(kind="str"), annotation="str", required=True)],
        outputs=[StateKey(key="zone", type=TypeRef(kind="str")), StateKey(key="maybe", guaranteed=False)],
    ),
    "m:update_zone": StepInfo(
        id="m:update_zone",
        name="Update zone",
        function="update_zone",
        module="m",
        category="m",
        kind="step",
        inputs=[
            StepInput(name="zone", type=TypeRef(kind="str"), annotation="str", required=True),
            StepInput(name="ttl", type=TypeRef(kind="int"), annotation="int", required=False, default=60),
        ],
    ),
    "m:count": StepInfo(
        id="m:count",
        name="Count",
        function="count",
        module="m",
        category="m",
        kind="step",
        inputs=[StepInput(name="zone", type=TypeRef(kind="list"), annotation="list", required=True)],
    ),
    "m:whole_state": StepInfo(
        id="m:whole_state",
        name="Whole state",
        function="whole_state",
        module="m",
        category="m",
        kind="step",
        usable=False,
        unusable_reason="reads the whole state",
    ),
}

CUSTOMER_FIELD = FormField(name="customer_name", type="string")


def definition(*step_ids: str, fields: list[FormField] | None = None, **configs: dict) -> WorkflowDefinition:
    return WorkflowDefinition(
        name="designed_test",
        description="Test",
        form_fields=[CUSTOMER_FIELD] if fields is None else fields,
        steps=[StepRef(step_id=step_id, config=configs.get(step_id.replace(":", "_"), {})) for step_id in step_ids],
    )


@pytest.mark.parametrize(
    ("steps", "errors"),
    [
        pytest.param(["m:load_zone", "m:update_zone"], [], id="chain-ok"),
        pytest.param(["m:update_zone"], [(0, "zone")], id="missing-input"),
        pytest.param(["m:update_zone", "m:load_zone"], [(0, "zone")], id="wrong-order"),
        pytest.param(["m:load_zone", "m:count"], [(1, "zone")], id="type-mismatch"),
        pytest.param(["m:whole_state"], [(0, None)], id="unusable-step"),
        pytest.param(["m:deleted"], [(0, None)], id="unknown-step"),
        pytest.param([], [(None, None)], id="no-steps"),
    ],
)
def test_validate_definition_errors(steps, errors):
    result = validate_definition(definition(*steps), STEPS)

    assert [(issue.position, issue.input) for issue in result.issues if issue.severity == "error"] == errors
    assert result.valid is not errors


def test_validate_definition_tracks_available_state():
    result = validate_definition(definition("m:load_zone", "m:update_zone"), STEPS)

    keys_per_position = [[state_key.key for state_key in state] for state in result.available]
    engine = ["process_id", "reporter", "workflow_name", "workflow_target"]
    # Keys a step only returns on some paths are not guaranteed, so they are not available to later steps.
    assert keys_per_position == [
        ["customer_name", *engine],
        ["customer_name", *engine, "zone"],
        ["customer_name", *engine, "zone"],
    ]


def test_validate_definition_helper_inputs_follow_config():
    template = {"template": "Zone {zone} for {customer_name}"}

    ok = validate_definition(definition("m:load_zone", "designer:log_message", designer_log_message=template), STEPS)
    missing = validate_definition(definition("designer:log_message", designer_log_message=template), STEPS)
    invalid = validate_definition(definition("designer:log_message", designer_log_message={"template": "{0}"}), STEPS)

    assert ok.valid
    assert [issue.input for issue in missing.issues] == ["zone"]
    assert "invalid configuration" in invalid.issues[0].message


def test_validate_definition_palette_statuses_at_position():
    result = validate_definition(definition("m:load_zone", fields=[]), STEPS, insert_at=0)

    assert result.palette is not None
    assert result.palette["m:load_zone"].status == "needs_form"
    assert [field.model_dump() for field in result.palette["m:load_zone"].suggested_fields] == [
        FormField(name="customer_name", type="string", title="Customer name").model_dump()
    ]
    assert result.palette["m:count"].status == "incompatible"
    assert result.palette["m:whole_state"].status == "unusable"
    assert result.palette["designer:set_value"].status == "ok"


def test_validate_definition_palette_suggests_subscription_picker(subscription_field_type):
    steps = {
        "m:needs_sub": StepInfo(
            id="m:needs_sub",
            name="Needs subscription",
            function="needs_sub",
            module="m",
            category="m",
            kind="step",
            inputs=[
                StepInput(
                    name="port",
                    type=TypeRef(kind="subscription", model="Sp", product_tags=["SP"], statuses=["active"]),
                    annotation="Sp",
                    required=True,
                    source="subscription_model",
                )
            ],
        )
    }

    result = validate_definition(definition(fields=[]), steps, insert_at=0)

    assert result.palette is not None
    suggestion = result.palette["m:needs_sub"].suggested_fields[0]
    assert (suggestion.type, suggestion.options.product_tags, suggestion.options.statuses) == (
        "subscription",
        ["SP"],
        ["active"],
    )


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"name": "task_x", "description": "x"}, id="missing-prefix"),
        pytest.param({"name": "designed_X", "description": "x"}, id="uppercase"),
        pytest.param({"name": "designed_x", "description": ""}, id="empty-description"),
        pytest.param(
            {"name": "designed_x", "description": "x", "form_fields": [{"name": "process_id", "type": "uuid"}]},
            id="reserved-field",
        ),
        pytest.param(
            {
                "name": "designed_x",
                "description": "x",
                "form_fields": [{"name": "a", "type": "string"}, {"name": "a", "type": "integer"}],
            },
            id="duplicate-field",
        ),
    ],
)
def test_workflow_definition_rejects(data):
    with pytest.raises(ValidationError):
        WorkflowDefinition.model_validate(data)
