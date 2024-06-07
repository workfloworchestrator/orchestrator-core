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

from orchestrator.cli.generator.generator.enums import get_int_enums, get_non_standard_fields, get_str_enums, to_dict
from orchestrator.cli.generator.generator.helpers import (
    create_dunder_init_files,
    get_product_path,
    get_product_types_folder,
    get_product_types_module,
    path_to_module,
    root_product_block,
)
from orchestrator.cli.generator.generator.settings import product_generator_settings as settings


def generate_product(context: dict) -> None:
    config = context["config"]
    environment = context["environment"]
    writer = context["writer"]

    product = config["type"]
    fixed_inputs = config.get("fixed_inputs", [])
    root_block = root_product_block(config)

    non_standard_fixed_inputs = get_non_standard_fields(fixed_inputs)
    int_enums = get_int_enums(fixed_inputs)
    str_enums = get_str_enums(fixed_inputs)

    template = environment.get_template("product.j2")
    content = template.render(
        product=product,
        product_blocks_module=path_to_module(settings.FOLDER_PREFIX / settings.PRODUCT_BLOCKS_PATH),
        product_types_module=get_product_types_module(),
        non_standard_fixed_inputs=non_standard_fixed_inputs,
        root_block=root_block,
        int_enums=int_enums,
        str_enums=str_enums,
        fixed_inputs=(to_dict(fixed_inputs) | to_dict(int_enums) | to_dict(str_enums)).values(),
    )

    path = get_product_path(config)
    writer(path, content)
    create_dunder_init_files(get_product_types_folder())
