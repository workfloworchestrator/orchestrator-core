# Copyright 2024-2026 SURF, GÉANT.
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

from collections.abc import Generator
from typing import TypeAlias, cast

from orchestrator.core.domain.base import ProductBlockModel
from orchestrator.core.forms import FormPage
from orchestrator.core.forms.validators import MigrationSummary, migration_summary
from pydantic import ConfigDict


def summary_form(product_name: str, summary_data: dict) -> Generator:
    ProductSummary: TypeAlias = cast("type[MigrationSummary]", migration_summary(summary_data))

    class SummaryForm(FormPage):
        model_config = ConfigDict(title=f"{product_name} summary")

        product_summary: ProductSummary

    yield SummaryForm


def create_summary_form(user_input: dict, product_name: str, fields: list[str]) -> Generator:
    columns = [[str(user_input[nm]) for nm in fields]]
    yield from summary_form(product_name, {"labels": fields, "columns": columns})


def modify_summary_form(user_input: dict, block: ProductBlockModel, fields: list[str]) -> Generator:
    before = [str(getattr(block, nm)) for nm in fields]  # type: ignore[attr-defined]
    after = [str(user_input[nm]) for nm in fields]
    yield from summary_form(
        block.subscription.product.name,
        {
            "labels": fields,
            "headers": ["Before", "After"],
            "columns": [before, after],
        },
    )
