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

from orchestrator.cli.generator.generator.fixed_input import (
    get_int_enum_fixed_inputs,
    get_non_standard_fixed_inputs,
    get_str_enum_fixed_inputs,
    replace_enum_fixed_inputs,
)
from orchestrator.cli.generator.generator.helpers import get_product_file_name, path_to_module, product_types_module
from orchestrator.cli.generator.generator.settings import product_generator_settings as settings


def get_product_path(config: dict) -> Path:
    file_name = get_product_file_name(config)
    return settings.FOLDER_PREFIX / settings.PRODUCT_TYPES_PATH / Path(file_name).with_suffix(".py")


def generate_product(context: dict) -> None:
    config = context["config"]
    environment = context["environment"]
    writer = context["writer"]

    product = config["type"]
    fixed_inputs = config.get("fixed_inputs", [])
    product_blocks = config.get("product_blocks", [])

    non_standard_fixed_inputs = get_non_standard_fixed_inputs(fixed_inputs)
    int_enums = get_int_enum_fixed_inputs(fixed_inputs)
    str_enums = get_str_enum_fixed_inputs(fixed_inputs)

    template = environment.get_template("product.j2")
    content = template.render(
        product=product,
        product_blocks_module=path_to_module(settings.FOLDER_PREFIX / settings.PRODUCT_BLOCKS_PATH),
        product_types_module=product_types_module,
        non_standard_fixed_inputs=non_standard_fixed_inputs,
        fixed_inputs=replace_enum_fixed_inputs(fixed_inputs),
        product_blocks=product_blocks,
        int_enums=int_enums,
        str_enums=str_enums,
    )

    path = get_product_path(config)
    writer(path, content)
