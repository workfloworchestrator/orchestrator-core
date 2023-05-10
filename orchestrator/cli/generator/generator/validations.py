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

from more_itertools import flatten

from orchestrator.cli.generator.generator.helpers import root_product_block


def get_all_validations(config: dict) -> list:
    def to_validations(field: dict) -> list[dict]:
        def to_validation(validation: dict) -> dict:
            return {"validation": validation, "field": field}

        return [to_validation(validation) for validation in field.get("validations", [])]

    product_block = root_product_block(config)
    return list(flatten(to_validations(field) for field in product_block["fields"]))


def get_validation_imports(validations: list) -> list:
    def format_validator(validation: dict) -> str:
        return f'{validation["validation"]["id"]}_validator'

    return [format_validator(validation) for validation in validations]


def get_validations(config: dict) -> tuple[list, list]:
    validations = get_all_validations(config)
    validation_imports = get_validation_imports(validations)

    return validations, validation_imports


def get_validations_for_modify(config: dict) -> tuple[list, list]:
    def modifiable(validation: dict) -> bool:
        return validation["field"].get("modifiable", True)

    validations = [validation for validation in get_all_validations(config) if modifiable(validation)]
    validation_imports = get_validation_imports(validations)

    return validations, validation_imports
