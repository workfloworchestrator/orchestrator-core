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

from unittest.mock import patch

import pytest

from orchestrator.core.search.core.types import EntityType, FilterOp, UIType
from orchestrator.core.search.filters import LtreeFilter, PathFilter
from orchestrator.core.search.query.exceptions import InvalidLtreePatternError
from orchestrator.core.search.query.validation import complete_filter_validation


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.is_lquery_syntactically_valid")
async def test_invalid_ltree_pattern_raises_error(mock_is_valid):
    """Invalid ltree patterns raise InvalidLtreePatternError."""
    mock_is_valid.return_value = False
    filter_with_invalid_ltree = PathFilter(
        path="subscription.path",
        condition=LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="invalid[pattern"),
        value_kind=UIType.COMPONENT,
    )
    with pytest.raises(InvalidLtreePatternError):
        await complete_filter_validation(filter_with_invalid_ltree, EntityType.SUBSCRIPTION)


@pytest.mark.asyncio
@patch("orchestrator.core.search.query.validation.is_lquery_syntactically_valid", return_value=True)
@patch("orchestrator.core.search.query.validation.validate_filter_path")
async def test_ltree_filter_takes_special_path(mock_validate_path, mock_lquery_valid):
    """LtreeFilter takes special validation path and does not call validate_filter_path."""
    filter_with_ltree = PathFilter(
        path="subscription.path",
        condition=LtreeFilter(op=FilterOp.MATCHES_LQUERY, value="*.product.*"),
        value_kind=UIType.COMPONENT,
    )
    await complete_filter_validation(filter_with_ltree, EntityType.SUBSCRIPTION)
    mock_validate_path.assert_not_called()
    mock_lquery_valid.assert_called_once()
