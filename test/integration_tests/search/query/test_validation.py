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

from unittest.mock import MagicMock, patch

import pytest

from orchestrator.core.search.core.types import EntityType, FilterOp, UIType
from orchestrator.core.search.filters import LtreeFilter, PathFilter
from orchestrator.core.search.query.exceptions import InvalidLtreePatternError
from orchestrator.core.search.query.validation import complete_filter_validation

pytestmark = pytest.mark.search


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.is_lquery_syntactically_valid")
async def test_complete_filter_ltree_valid_syntax_passes(mock_is_valid: MagicMock):
    """LtreeFilter with valid syntax should not raise."""
    mock_is_valid.return_value = True
    pf = PathFilter(
        path="subscription.path",
        condition=LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="*.valid.*"),
        value_kind=UIType.COMPONENT,
    )
    await complete_filter_validation(pf, EntityType.SUBSCRIPTION)


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.is_lquery_syntactically_valid")
async def test_complete_filter_ltree_invalid_syntax_raises(mock_is_valid: MagicMock):
    """LtreeFilter with invalid syntax raises InvalidLtreePatternError."""
    mock_is_valid.return_value = False
    pf = PathFilter(
        path="subscription.path",
        condition=LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="invalid[pattern"),
        value_kind=UIType.COMPONENT,
    )
    with pytest.raises(InvalidLtreePatternError):
        await complete_filter_validation(pf, EntityType.SUBSCRIPTION)
