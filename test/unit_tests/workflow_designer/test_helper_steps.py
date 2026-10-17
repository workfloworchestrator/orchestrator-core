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

from types import SimpleNamespace
from unittest import mock

import pytest
from pydantic import ValidationError

from orchestrator.core.utils.functional import orig
from orchestrator.core.workflow_designer import helper_steps
from orchestrator.core.workflow_designer.helper_steps import (
    HELPERS,
    LoadSubscriptionInfoConfig,
    LogMessageConfig,
    SetValueConfig,
    helper_step_infos,
    placeholders,
)
from pydantic_forms.core import post_form
from pydantic_forms.exceptions import FormNotCompleteError


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param({"key": "zone", "value": "x"}, "x", id="str"),
        pytest.param({"key": "count", "type": "int", "value": "5"}, 5, id="int-from-text"),
        pytest.param({"key": "ratio", "type": "float", "value": "0.5"}, 0.5, id="float-from-text"),
        pytest.param({"key": "flag", "type": "bool", "value": "false"}, False, id="bool-false-text"),
        pytest.param({"key": "flag", "type": "bool", "value": "yes"}, True, id="bool-yes-text"),
        pytest.param({"key": "flag", "type": "bool", "value": True}, True, id="bool"),
    ],
)
def test_set_value_config_coerces_value(config, expected):
    assert SetValueConfig.model_validate(config).value == expected


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({"key": "count", "type": "int", "value": "many"}, id="not-an-int"),
        pytest.param({"key": "process_id", "value": "x"}, id="reserved-key"),
        pytest.param({"key": "Not A Key", "value": "x"}, id="invalid-key"),
    ],
)
def test_set_value_config_rejects(config):
    with pytest.raises(ValidationError):
        SetValueConfig.model_validate(config)


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        pytest.param("Done", [], id="no-placeholders"),
        pytest.param("{zone} for {customer} in {zone}", ["zone", "customer"], id="deduplicated-in-order"),
        pytest.param("{{literal}} braces", [], id="escaped-braces"),
    ],
)
def test_placeholders(template, expected):
    assert placeholders(template) == expected


@pytest.mark.parametrize("template", ["{0}", "{zone.name}", "{zone", "{zone[0]}"])
def test_log_message_rejects_non_key_placeholders(template):
    with pytest.raises(ValidationError):
        LogMessageConfig.model_validate({"template": template})


def test_set_value_step_returns_value():
    step = HELPERS["designer:set_value"].build(SetValueConfig(key="count", type="int", value=3))

    assert step.name == "Set count"
    assert orig(step)() == {"count": 3}


def test_log_message_step_appends_to_log():
    step = HELPERS["designer:log_message"].build(LogMessageConfig(template="{zone} has {count}"))

    result = orig(step)({"zone": "a", "count": 2, "designer_log": ["before"]})

    assert result == {"designer_log": ["before", "a has 2"]}


def test_load_subscription_info_step_prefixes_keys():
    subscription = SimpleNamespace(
        description="Port",
        status="active",
        insync=True,
        product=SimpleNamespace(name="Port 10G", tag="PORT"),
        customer_id="c1",
    )
    step = HELPERS["designer:load_subscription_info"].build(LoadSubscriptionInfoConfig(prefix="sub_"))

    with mock.patch.object(helper_steps.subscriptions, "get_subscription", return_value=subscription) as get:
        result = orig(step)({"subscription_id": "s1"})

    get.assert_called_once_with("s1")
    assert result == {
        "sub_description": "Port",
        "sub_status": "active",
        "sub_insync": True,
        "sub_product_name": "Port 10G",
        "sub_product_tag": "PORT",
        "sub_customer_id": "c1",
    }


def test_confirm_step_pauses_with_a_translated_form():
    step = HELPERS["designer:confirm"].build(helper_steps.ConfirmConfig(message="Sure?"))

    with pytest.raises(FormNotCompleteError) as error:
        post_form(step.form, {}, [])
    assert error.value.form["properties"]["designer_confirmation"]["default"]["message"] == "Sure?"
    assert post_form(step.form, {}, [{"accept_designer_confirmation": "ACCEPTED"}]) == {"confirmed": True}


def test_helper_step_infos_describe_default_config():
    infos = helper_step_infos()

    assert set(infos) == set(HELPERS)
    assert [i.name for i in infos["designer:log_message"].inputs] == []
    assert [o.key for o in infos["designer:set_value"].outputs] == ["value"]
    assert infos["designer:confirm"].pauses is True
    assert all(info.kind == "helper" and info.config_schema for info in infos.values())
