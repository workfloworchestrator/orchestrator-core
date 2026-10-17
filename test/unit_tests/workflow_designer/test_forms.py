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

"""Forms are built in `orchestrator.core.workflow_designer`, so core's translation check applies to their field names."""

import pytest

from orchestrator.core.workflow_designer import forms
from orchestrator.core.workflow_designer.forms import FieldOptions, FormField, build_initial_form, suggest_field
from orchestrator.core.workflow_designer.type_refs import TypeRef
from pydantic_forms.core import post_form
from pydantic_forms.exceptions import FormNotCompleteError, FormValidationError


def form(*fields: FormField):
    return build_initial_form(list(fields), "Test form")


def test_initial_form_schema():
    generator = form(
        FormField(name="note", type="string", title="Note"),
        FormField(name="version", type="integer", required=False, default=3),
        FormField(name="task", type="choice", options=FieldOptions(choices=["a", "b"])),
    )

    with pytest.raises(FormNotCompleteError) as error:
        post_form(generator, {}, [])

    schema = error.value.form
    assert schema["title"] == "Test form"
    assert schema["required"] == ["note", "task"]
    assert schema["properties"]["note"]["title"] == "Note"
    assert schema["properties"]["version"]["default"] == 3


@pytest.mark.parametrize(
    ("user_input", "expected"),
    [
        pytest.param({"note": "hi"}, {"note": "hi", "version": None}, id="optional-omitted"),
        pytest.param({"note": "hi", "version": "5"}, {"note": "hi", "version": 5}, id="coerced"),
    ],
)
def test_initial_form_output(user_input, expected):
    generator = form(FormField(name="note", type="string"), FormField(name="version", type="integer", required=False))

    assert post_form(generator, {}, [user_input]) == expected


@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param({}, id="required-missing"),
        pytest.param({"note": "hi", "version": "many"}, id="not-an-int"),
        pytest.param({"note": "hi", "unexpected": 1}, id="extra-field"),
    ],
)
def test_initial_form_rejects(user_input):
    generator = form(FormField(name="note", type="string"), FormField(name="version", type="integer", required=False))

    with pytest.raises(FormValidationError):
        post_form(generator, {}, [user_input])


def test_choice_field_only_accepts_its_choices():
    generator = form(FormField(name="task", type="choice", options=FieldOptions(choices=["a", "b"])))

    assert post_form(generator, {}, [{"task": "a"}]) == {"task": "a"}
    with pytest.raises(FormValidationError):
        post_form(generator, {}, [{"task": "c"}])


@pytest.mark.parametrize(
    ("name", "ref", "expected_type"),
    [
        pytest.param("zone", TypeRef(kind="str"), "string", id="str"),
        pytest.param("count", TypeRef(kind="int"), "integer", id="int"),
        pytest.param("enabled", TypeRef(kind="bool"), "boolean", id="bool"),
        pytest.param("process_ref", TypeRef(kind="uuid"), "uuid", id="uuid"),
        pytest.param("customer_id", TypeRef(kind="uuid"), "customer", id="customer-by-name"),
        pytest.param("subscription_id", TypeRef(kind="uuid"), "uuid", id="no-subscription-picker-in-core"),
        pytest.param("payload", TypeRef(kind="dict"), None, id="no-form-field-for-dict"),
    ],
)
def test_suggest_field(name, ref, expected_type):
    suggestion = suggest_field(name, ref)

    assert (suggestion.type if suggestion else None) == expected_type


def test_registered_field_type_takes_precedence_in_suggestions(subscription_field_type):
    ref = TypeRef(kind="subscription", model="Port", product_tags=["PORT"], statuses=["active"])

    suggestion = suggest_field("port", ref)

    assert suggestion is not None
    assert (suggestion.type, suggestion.options.product_tags, suggestion.options.statuses) == (
        "subscription",
        ["PORT"],
        ["active"],
    )
    assert suggest_field("subscription_id", TypeRef(kind="uuid")).type == "subscription"


def test_unknown_field_type_has_any_state_type():
    assert forms.field_state_type(FormField(name="note", type="does_not_exist")) == TypeRef()


@pytest.mark.parametrize("name", ["process_id", "reporter", "workflow_name", "workflow_target", "state"])
def test_reserved_field_names(name):
    with pytest.raises(ValueError, match="set by the workflow engine"):
        FormField(name=name, type="string")
