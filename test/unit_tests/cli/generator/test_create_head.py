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

from unittest import mock

from orchestrator.core.cli.generate import get_template_environment
from orchestrator.core.cli.generator.generator.migration import create_data_head_if_not_exists


@mock.patch("orchestrator.core.cli.generator.generator.migration.get_heads")
def test_revision_with_data_head(mock_get_heads):
    mock_get_heads.return_value = {"schema": "19552eeb4edf"}
    mock_writer = mock.MagicMock()
    context = {"writer": mock_writer, "environment": get_template_environment()}

    create_data_head_if_not_exists(context)

    mock_writer.assert_called_once()
    assert 'branch_labels = ("data",)\ndepends_on = "19552eeb4edf"' in mock_writer.call_args[0][1]


@mock.patch("orchestrator.core.cli.generator.generator.migration.get_heads")
def test_revision_without_data_head(get_heads):
    get_heads.return_value = {"schema": "19552eeb4edf", "data": "14830435134e"}
    mock_writer = mock.MagicMock()
    context = {"writer": mock_writer, "environment": get_template_environment()}

    create_data_head_if_not_exists(context)
    mock_writer.assert_not_called()
