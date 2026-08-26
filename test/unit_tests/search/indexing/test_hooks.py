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

"""Tests for the process-exit indexing hook: state extraction, entity indexing and strictness."""

from types import SimpleNamespace
from unittest.mock import call, patch
from uuid import uuid4

import pytest

from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.indexing.hooks import extract_subscription_ids, index_process_and_subscriptions
from orchestrator.core.settings import llm_settings
from orchestrator.core.workflow import (
    Abort,
    AwaitingCallback,
    Complete,
    Failed,
    Skipped,
    Success,
    Suspend,
    Waiting,
)

pytestmark = pytest.mark.search

SUB_ID_A = str(uuid4())
SUB_ID_B = str(uuid4())


@pytest.mark.parametrize(
    "state,expected",
    [
        pytest.param({}, set(), id="empty-state"),
        pytest.param({"unrelated": "value"}, set(), id="no-subscription-keys"),
        pytest.param({"subscription_id": SUB_ID_A}, {SUB_ID_A}, id="subscription-id-str"),
        pytest.param({"subscription_id": None}, set(), id="subscription-id-none"),
        pytest.param({"subscription": {"subscription_id": SUB_ID_A}}, {SUB_ID_A}, id="subscription-serialized-dict"),
        pytest.param(
            {"subscription": SimpleNamespace(subscription_id=SUB_ID_A)}, {SUB_ID_A}, id="subscription-model-like"
        ),
        pytest.param({"subscriptions": [SUB_ID_A, SUB_ID_B]}, {SUB_ID_A, SUB_ID_B}, id="subscriptions-list-of-str"),
        pytest.param(
            {"subscriptions": [{"subscription_id": SUB_ID_A}, SimpleNamespace(subscription_id=SUB_ID_B)]},
            {SUB_ID_A, SUB_ID_B},
            id="subscriptions-list-mixed",
        ),
        pytest.param({"subscription_ids": (SUB_ID_A, SUB_ID_B)}, {SUB_ID_A, SUB_ID_B}, id="subscription-ids-tuple"),
        pytest.param(
            {"subscription": SimpleNamespace(subscription_id=SUB_ID_A), "subscription_id": SUB_ID_A},
            {SUB_ID_A},
            id="duplicates-deduped",
        ),
        pytest.param({"subscription": "not-a-uuid-but-a-string"}, {"not-a-uuid-but-a-string"}, id="opaque-string"),
        pytest.param({"subscription": 42}, set(), id="unsupported-type-ignored"),
        pytest.param("not-a-dict", set(), id="state-not-a-dict"),
        pytest.param(None, set(), id="state-none"),
    ],
)
def test_extract_subscription_ids(state, expected):
    assert extract_subscription_ids(state) == expected


def test_extract_subscription_ids_accepts_uuid_objects():
    subscription_id = uuid4()
    assert extract_subscription_ids({"subscription_id": subscription_id}) == {str(subscription_id)}


@pytest.mark.parametrize(
    "process_variant",
    [
        pytest.param(Success, id="success"),
        pytest.param(Skipped, id="skipped"),
        pytest.param(Complete, id="complete"),
        pytest.param(Suspend, id="suspend"),
        pytest.param(Abort, id="abort"),
        pytest.param(Waiting, id="waiting"),
        pytest.param(AwaitingCallback, id="awaiting-callback"),
        pytest.param(Failed, id="failed"),
    ],
)
@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_process_is_always_indexed(mock_run_indexing, process_variant):
    process_id = uuid4()

    index_process_and_subscriptions(process_id, process_variant({}))

    mock_run_indexing.assert_called_once_with(EntityType.PROCESS, str(process_id))


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_subscriptions_from_state_are_indexed(mock_run_indexing):
    process_id = uuid4()

    index_process_and_subscriptions(process_id, Success({"subscription_id": SUB_ID_A}))

    assert mock_run_indexing.call_args_list == [
        call(EntityType.PROCESS, str(process_id)),
        call(EntityType.SUBSCRIPTION, SUB_ID_A),
    ]


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_non_dict_state_still_indexes_process(mock_run_indexing):
    process_id = uuid4()

    index_process_and_subscriptions(process_id, Failed(RuntimeError("boom")))

    mock_run_indexing.assert_called_once_with(EntityType.PROCESS, str(process_id))


@patch("orchestrator.core.search.indexing.hooks.logger")
@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_indexing_error_is_swallowed_when_not_strict(mock_run_indexing, mock_logger, monkeypatch):
    monkeypatch.setattr(llm_settings, "SEARCH_INDEXING_STRICT", False)
    process_id = uuid4()
    mock_run_indexing.side_effect = RuntimeError("index error")

    index_process_and_subscriptions(process_id, Success({}))  # must not raise

    # Swallowing is only acceptable if the failure is still observable in the logs.
    mock_logger.warning.assert_called_once()
    _, kwargs = mock_logger.warning.call_args
    assert kwargs["entity_type"] == EntityType.PROCESS
    assert kwargs["entity_id"] == str(process_id)
    assert "index error" in kwargs["error"]


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_malformed_subscription_id_is_skipped_but_process_is_still_indexed(mock_run_indexing, monkeypatch):
    """A human-readable label under a subscription key must not disable indexing for the exit."""
    monkeypatch.setattr(llm_settings, "SEARCH_INDEXING_STRICT", False)
    process_id = uuid4()

    index_process_and_subscriptions(process_id, Success({"subscription": "not-a-uuid-but-a-string"}))

    mock_run_indexing.assert_called_once_with(EntityType.PROCESS, str(process_id))


@patch("orchestrator.core.search.indexing.hooks.logger")
@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_skipped_subscription_candidate_is_logged(mock_run_indexing, mock_logger, monkeypatch):
    """Dropping a candidate silently would hide a future state-shape regression completely."""
    monkeypatch.setattr(llm_settings, "SEARCH_INDEXING_STRICT", False)
    process_id = uuid4()

    index_process_and_subscriptions(process_id, Success({"subscription": "not-a-uuid-but-a-string"}))

    mock_logger.debug.assert_called_once()
    _, kwargs = mock_logger.debug.call_args
    assert kwargs["candidate"] == "not-a-uuid-but-a-string"
    assert kwargs["process_id"] == str(process_id)


@patch("orchestrator.core.search.indexing.hooks.logger")
@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_valid_subscription_id_is_not_logged_as_skipped(mock_run_indexing, mock_logger, monkeypatch):
    """The debug log must stay quiet for real traffic, otherwise it is noise nobody reads."""
    monkeypatch.setattr(llm_settings, "SEARCH_INDEXING_STRICT", False)

    index_process_and_subscriptions(uuid4(), Success({"subscription_id": SUB_ID_A}))

    mock_logger.debug.assert_not_called()


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_malformed_subscription_id_does_not_hide_a_valid_one(mock_run_indexing, monkeypatch):
    monkeypatch.setattr(llm_settings, "SEARCH_INDEXING_STRICT", False)
    process_id = uuid4()

    index_process_and_subscriptions(process_id, Success({"subscriptions": ["a-label", SUB_ID_A]}))

    assert mock_run_indexing.call_args_list == [
        call(EntityType.PROCESS, str(process_id)),
        call(EntityType.SUBSCRIPTION, SUB_ID_A),
    ]


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_failing_process_index_does_not_skip_subscriptions(mock_run_indexing, monkeypatch):
    monkeypatch.setattr(llm_settings, "SEARCH_INDEXING_STRICT", False)

    def fail_the_process(entity_type, entity_id):
        if entity_type == EntityType.PROCESS:
            raise RuntimeError("process index error")

    mock_run_indexing.side_effect = fail_the_process

    index_process_and_subscriptions(uuid4(), Success({"subscription_id": SUB_ID_A}))

    assert call(EntityType.SUBSCRIPTION, SUB_ID_A) in mock_run_indexing.call_args_list


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_one_failing_subscription_does_not_skip_the_rest(mock_run_indexing, monkeypatch):
    monkeypatch.setattr(llm_settings, "SEARCH_INDEXING_STRICT", False)

    def fail_subscription_a(entity_type, entity_id):
        if entity_id == SUB_ID_A:
            raise RuntimeError("subscription index error")

    mock_run_indexing.side_effect = fail_subscription_a

    # extract_subscription_ids returns a set, so patch it to pin the order and keep the test deterministic:
    # the failing subscription must come first for this to prove the second one is still reached.
    with patch("orchestrator.core.search.indexing.hooks.extract_subscription_ids", return_value=[SUB_ID_A, SUB_ID_B]):
        index_process_and_subscriptions(uuid4(), Success({"subscriptions": [SUB_ID_A, SUB_ID_B]}))

    assert call(EntityType.SUBSCRIPTION, SUB_ID_A) in mock_run_indexing.call_args_list
    assert call(EntityType.SUBSCRIPTION, SUB_ID_B) in mock_run_indexing.call_args_list


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_subscription_indexing_error_is_raised_when_strict(mock_run_indexing, monkeypatch):
    """Strict mode must re-raise per entity, not only for the process."""
    monkeypatch.setattr(llm_settings, "SEARCH_INDEXING_STRICT", True)

    def fail_subscription_a(entity_type, entity_id):
        if entity_id == SUB_ID_A:
            raise RuntimeError("subscription index error")

    mock_run_indexing.side_effect = fail_subscription_a

    with pytest.raises(RuntimeError, match="subscription index error"):
        index_process_and_subscriptions(uuid4(), Success({"subscription_id": SUB_ID_A}))


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_indexing_error_is_raised_when_strict(mock_run_indexing, monkeypatch):
    monkeypatch.setattr(llm_settings, "SEARCH_INDEXING_STRICT", True)
    mock_run_indexing.side_effect = RuntimeError("index error")

    with pytest.raises(RuntimeError, match="index error"):
        index_process_and_subscriptions(uuid4(), Success({}))
