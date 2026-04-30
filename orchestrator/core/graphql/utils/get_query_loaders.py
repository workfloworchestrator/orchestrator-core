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

from sqlalchemy.orm import Load

from orchestrator.core.db.database import BaseModel as DbBaseModel
from orchestrator.core.db.loaders import (
    get_query_loaders_for_model_paths,
)
from orchestrator.core.graphql.types import OrchestratorInfo
from orchestrator.core.graphql.utils.get_selected_paths import get_selected_paths


def get_query_loaders_for_gql_fields(root_model: type[DbBaseModel], info: OrchestratorInfo) -> list[Load]:
    """Get sqlalchemy query loaders for the given GraphQL query.

    Based on the GraphQL query's selected fields, returns the required DB loaders to use
    in SQLALchemy's `.options()` for efficiently quering (nested) relationships.
    """
    model_paths = [path.removeprefix("page.") for path in get_selected_paths(info)]

    return get_query_loaders_for_model_paths(root_model, model_paths)
