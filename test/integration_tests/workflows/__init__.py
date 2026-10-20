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

"""Workflow test helpers.

The helpers live in :mod:`orchestrator.core.testing`, which is shipped with the ``testing`` extra. They are
re-exported here so existing imports keep working; new tests should import from ``orchestrator.core.testing``.
"""

from functools import reduce

from orchestrator.core.testing import (
    WorkflowInstanceForTests,
    assert_aborted,
    assert_assignee,
    assert_awaiting_callback,
    assert_complete,
    assert_failed,
    assert_state,
    assert_state_equal,
    assert_step_name,
    assert_success,
    assert_suspended,
    assert_waiting,
    delete_workflow,
    extract_error,
    extract_state,
    resume_workflow,
    run_form_generator,
    run_workflow,
    store_workflow,
)
from test.integration_tests.config import IMS_CIRCUIT_ID, PORT_SUBSCRIPTION_ID

__all__ = [
    "WorkflowInstanceForTests",
    "assert_aborted",
    "assert_assignee",
    "assert_awaiting_callback",
    "assert_complete",
    "assert_failed",
    "assert_product_blocks_equal",
    "assert_state",
    "assert_state_equal",
    "assert_step_name",
    "assert_success",
    "assert_suspended",
    "assert_waiting",
    "delete_workflow",
    "extract_error",
    "extract_state",
    "resume_workflow",
    "run_form_generator",
    "run_workflow",
    "store_workflow",
]


def assert_product_blocks_equal(expected, actual):
    def key_value_sort(item):
        name = list(item.keys())[0]
        if name == "Virtual Circuit":
            items = list(filter(lambda k: list(k.keys())[0] == IMS_CIRCUIT_ID, item["Virtual Circuit"]))
            id_ = items[0][IMS_CIRCUIT_ID]
            return f"1_{id_}"
        if name == "Service Attach Point":
            port_subscription_id = list(
                filter(lambda k: list(k.keys())[0] == PORT_SUBSCRIPTION_ID, item["Service Attach Point"])
            )
            port_subscription_id = port_subscription_id[0][PORT_SUBSCRIPTION_ID]
            vlanrange = list(filter(lambda k: list(k.keys())[0] == "vlanrange", item["Service Attach Point"]))
            vlanrange = vlanrange[0]["vlanrange"]
            return f"2_{port_subscription_id}_{vlanrange}"
        return name

    expected.sort(key=key_value_sort)
    actual.sort(key=key_value_sort)

    def accumulate_list_of_tuples(acc: list, dikt: dict) -> list[tuple]:
        acc.extend(dikt.items())
        return acc

    expected_product_block_names = [list(p.keys())[0] for p in expected]
    actual_product_block_names = [list(p.keys())[0] for p in actual]
    assert expected_product_block_names == actual_product_block_names, (
        f"Expected the following product blocks: {expected_product_block_names}, but got {actual_product_block_names}"
    )

    for expected_pb, actual_pb in zip(expected, actual):
        for expected_instance_values, actual_instance_values in zip(expected_pb.values(), actual_pb.values()):
            expected_tuples = set(reduce(accumulate_list_of_tuples, expected_instance_values, []))
            actual_tuples = set(reduce(accumulate_list_of_tuples, actual_instance_values, []))
            missing_instance_values = expected_tuples - actual_tuples
            unexpected_instance_values = actual_tuples - expected_tuples
            assert not missing_instance_values, (
                f"Missing instance value(s): {missing_instance_values}; Unexpected: {unexpected_instance_values}"
            )
            assert not unexpected_instance_values, f"Unexpected instance values: {unexpected_instance_values}"
