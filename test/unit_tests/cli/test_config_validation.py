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

import pytest
import structlog

from orchestrator.core.cli.generate import app as generate_app
from test.unit_tests.cli.helpers import absolute_path

logger = structlog.get_logger()


@pytest.mark.parametrize(
    "config_file,expected_exception,expected_message",
    [
        ("invalid_product_config1.yaml", ValueError, "found multiple"),
        ("invalid_product_config2.yaml", ValueError, "Cycle detected"),
    ],
)
def test_product_block_validation(config_file, expected_exception, expected_message, cli_invoke):
    config_file = absolute_path(config_file)
    with pytest.raises(expected_exception, match=expected_message):
        cli_invoke(generate_app, ["product-blocks", "--config-file", config_file])
