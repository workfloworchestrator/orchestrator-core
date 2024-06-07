import pytest
import structlog

from orchestrator.cli.generate import app as generate_app
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
