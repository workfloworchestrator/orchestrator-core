# Copyright 2022-2023 SURF.
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
from orchestrator.graphql.schemas.product import ProductModelGraphql
from orchestrator.graphql.schemas.strawberry_pydantic_patch import (
    convert_pydantic_model_to_strawberry_class__patched,  # noqa: F401
)
from orchestrator.graphql.types import StrawberryModelType

DEFAULT_GRAPHQL_MODELS: StrawberryModelType = {
    "ProductModelGraphql": ProductModelGraphql,
}
