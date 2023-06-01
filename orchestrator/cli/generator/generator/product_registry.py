from typing import Callable, Generator

import structlog

from orchestrator.cli.generator.generator.helpers import get_product_import, insert_into_imports
from orchestrator.cli.generator.generator.settings import product_generator_settings

logger = structlog.getLogger(__name__)


def update_product_registry(context: dict) -> None:
    config = context["config"]
    writer = context["writer"]

    path = product_generator_settings.PRODUCT_REGISTRY_PATH

    try:
        with open(path) as stream:
            original_content = stream.readlines()
    except FileNotFoundError:
        logger.info("File with product registry dispatch not found yet, creating", path=path)
        original_content = [
            "from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY\n",
            "\n" "SUBSCRIPTION_MODEL_REGISTRY.update(\n",
            "   {\n",
            "   }\n" ")\n",
        ]

    product = config
    product_import = get_product_import(product)

    content_with_import = insert_into_imports(original_content, product_import)

    product_declaration = f'        "{config["name"]}": {config["type"]},\n'
    updated_content = insert_into_product_registry(content_with_import, product_declaration)

    writer(path, "".join(updated_content))


def insert_into_product_registry(content: list[str], product_declaration: str) -> list[str]:
    # Note: we may consider using a real Python parser here someday, but for now this is ok and formatting
    # gets done by isort and black.
    def produce() -> Generator:
        not_inserted_yet = True
        for line in content:
            # first closing bracket marks the end of the registry definition
            if "}" in line and not_inserted_yet:
                yield product_declaration
                not_inserted_yet = False
            yield line

    return [*produce()]
