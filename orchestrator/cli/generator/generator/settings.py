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

from pydantic import BaseSettings


class ProductGeneratorSettings(BaseSettings):
    PRODUCT_TYPES_PATH: str = "surf/products/product_types"
    PRODUCT_BLOCKS_PATH: str = "surf/products/product_blocks"
    EMAIL_TEMPLATE_PATH: str = "surf/products/services/mail_templates/product_types"
    WORKFLOWS_PATH: str = "surf/workflows"
    TEST_PRODUCT_TYPE_PATH: str = "test/unit_tests/domain/product_types"
    TEST_WORKFLOWS_PATH: str = "test/unit_tests/workflows"

    # Files that will be updated
    PRODUCT_REGISTRY_PATH: str = "surf/products/__init__.py"
    SUBSCRIPTION_DESCRIPTION_PATH: str = "surf/products/services/subscription.py"
    TRANSLATION_PATH: str = "surf/translations/en-GB.json"
    MAIL_SINGLE_DISPATCH_PATH: str = "surf/products/services/mail.py"


product_generator_settings = ProductGeneratorSettings()
