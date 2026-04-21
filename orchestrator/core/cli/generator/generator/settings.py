# Copyright 2019-2020 SURF.
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
from pathlib import Path

from pydantic_settings import BaseSettings


class ProductGeneratorSettings(BaseSettings):
    FOLDER_PREFIX: Path = Path("")
    CUSTOM_TEMPLATES: Path = Path("")

    PRODUCT_TYPES_PATH: Path = Path("products/product_types")
    PRODUCT_BLOCKS_PATH: Path = Path("products/product_blocks")
    WORKFLOWS_PATH: Path = Path("workflows")
    TEST_PRODUCT_TYPE_PATH: Path = Path("test/unit_tests/domain/product_types")
    TEST_WORKFLOWS_PATH: Path = Path("test/unit_tests/workflows")

    # Files that will be updated
    PRODUCT_REGISTRY_PATH: Path = Path("products/__init__.py")
    SUBSCRIPTION_DESCRIPTION_PATH: Path = Path("products/services/subscription.py")
    TRANSLATION_PATH: Path = Path("translations/en-GB.json")


product_generator_settings = ProductGeneratorSettings()
