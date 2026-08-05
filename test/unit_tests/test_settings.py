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

import json

import pytest
from pydantic import ValidationError

from orchestrator.core.settings import AppSettings
from orchestrator.core.targets import Target


def test_celery_target_queues_defaults_to_empty_mapping():
    assert AppSettings().CELERY_TARGET_QUEUES == {}


def test_celery_target_queues_env_var_json_round_trip(monkeypatch):
    """Enum-keyed dict must parse from the JSON env-var source (pydantic-settings v2 smoke test)."""
    monkeypatch.setenv("CELERY_TARGET_QUEUES", json.dumps({"RECONCILE": "reconcile", "VALIDATE": "validate"}))

    settings = AppSettings()

    assert settings.CELERY_TARGET_QUEUES == {Target.RECONCILE: "reconcile", Target.VALIDATE: "validate"}


@pytest.mark.parametrize(
    "value",
    [
        pytest.param({"DOES_NOT_EXIST": "some-queue"}, id="unknown-target-key"),
        pytest.param({"RECONCILE": ""}, id="empty-queue-name"),
        pytest.param({"RECONCILE": "   "}, id="whitespace-only-queue-name"),
    ],
)
def test_celery_target_queues_rejects_invalid_mapping(value):
    with pytest.raises(ValidationError):
        AppSettings(CELERY_TARGET_QUEUES=value)


def test_celery_target_queues_rejects_invalid_env_var_at_startup(monkeypatch):
    monkeypatch.setenv("CELERY_TARGET_QUEUES", json.dumps({"NOT_A_TARGET": "queue"}))

    with pytest.raises(ValidationError):
        AppSettings()
