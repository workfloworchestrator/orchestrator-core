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

"""Builders for seeding the search index and filtering it in retrieval integration tests."""

from orchestrator.core.search.core.types import BooleanOperator, FilterOp, UIType
from orchestrator.core.search.filters import EqualityFilter, FilterTree, PathFilter
from orchestrator.core.settings import llm_settings
from test.integration_tests.search._helpers import index_row

__all__ = ["and_tree", "eq_leaf", "index_row", "vec"]


def vec(axis: int) -> list[float]:
    """A unit vector on one axis, so distances between seeded embeddings are controllable."""
    vector = [0.0] * llm_settings.EMBEDDING_DIMENSION
    vector[axis] = 1.0
    return vector


def eq_leaf(path: str, value: str) -> PathFilter:
    return PathFilter(path=path, condition=EqualityFilter(op=FilterOp.EQ, value=value), value_kind=UIType.STRING)


def and_tree(*leaves: PathFilter) -> FilterTree:
    return FilterTree(op=BooleanOperator.AND, children=list(leaves))
