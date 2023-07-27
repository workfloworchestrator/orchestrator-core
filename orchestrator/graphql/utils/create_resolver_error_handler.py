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

from graphql import GraphQLError

from orchestrator.db.filters import CallableErrorHandler
from orchestrator.graphql.extensions.error_collector_extension import register_error
from orchestrator.graphql.types import OrchestratorInfo


def create_resolver_error_handler(info: OrchestratorInfo) -> CallableErrorHandler:
    def _handle_error(message: str, **kwargs) -> None:  # type: ignore
        register_error(GraphQLError(message=message, path=info.path, extensions=(kwargs or {})))

    return _handle_error
