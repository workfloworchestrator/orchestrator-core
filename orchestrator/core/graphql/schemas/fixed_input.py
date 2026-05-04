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

import strawberry

from orchestrator.core.schemas.fixed_input import FixedInputConfigurationItemSchema, FixedInputSchema, TagConfig


@strawberry.experimental.pydantic.type(model=FixedInputSchema, all_fields=True)
class FixedInput:
    pass


@strawberry.experimental.pydantic.type(model=FixedInputConfigurationItemSchema, all_fields=True)
class FixedInputConfigurationItem:
    pass


@strawberry.input
class FixedInputConfigurationInputType:
    fixed_inputs: list[FixedInputConfigurationItem]
    by_tag: TagConfig
