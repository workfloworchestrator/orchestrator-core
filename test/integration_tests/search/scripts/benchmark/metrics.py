# Copyright 2019-2025 SURF, GÉANT.
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


def calculate_spearman_correlation(predicted: list[str], expected: list[str]) -> float:
    """Calculate Spearman's rank correlation coefficient.

    Returns value between -1 and 1 (1.0 = identical rankings, 0.0 = no correlation).
    """
    if not expected or not predicted:
        return 0.0

    common_items = set(predicted) & set(expected)
    if len(common_items) < 2:
        return 0.0

    predicted_ranks = {item: rank for rank, item in enumerate(predicted) if item in common_items}
    expected_ranks = {item: rank for rank, item in enumerate(expected) if item in common_items}

    n = len(common_items)
    sum_d_squared = sum((predicted_ranks[item] - expected_ranks[item]) ** 2 for item in common_items)

    if n <= 1:
        return 0.0

    return 1.0 - (6.0 * sum_d_squared) / (n * (n * n - 1))


def calculate_top_k_overlap(predicted: list[str], expected: list[str], k_values: list[int]) -> dict[int, float]:
    """Calculate what fraction of top-K results appear in ground truth top-K."""
    results = {}

    for k in k_values:
        predicted_top_k = set(predicted[:k])
        expected_top_k = set(expected[:k])

        if not expected_top_k:
            results[k] = 0.0
            continue

        overlap = len(predicted_top_k & expected_top_k)
        results[k] = overlap / min(k, len(expected_top_k))

    return results
