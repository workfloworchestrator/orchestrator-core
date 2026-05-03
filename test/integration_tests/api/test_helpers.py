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

from orchestrator.core.api.helpers import product_block_paths


def test_product_block_paths(sub_list_union_overlap_subscription_1):
    paths = product_block_paths(sub_list_union_overlap_subscription_1)
    assert paths == [
        "product",
        "test_block.sub_block",
        "test_block.sub_block_2",
        "test_block.sub_block_list.0",
        "test_block",
        "list_union_blocks.0",
        "list_union_blocks.1",
    ]

    # Check that SubscriptionModel and subscription dict work the same
    assert product_block_paths(sub_list_union_overlap_subscription_1) == product_block_paths(
        sub_list_union_overlap_subscription_1.model_dump()
    )
