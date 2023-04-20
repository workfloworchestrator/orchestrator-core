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

from typing import Any, Generator

from graphql import GraphQLError
from strawberry.extensions import SchemaExtension

from orchestrator.graphql.types import CustomInfo


class ErrorCollectorExtension(SchemaExtension):
    errors: list[GraphQLError] = []

    def resolve(self, _next: Any, root: Any, info: CustomInfo, *args, **kwargs) -> Any:  # type: ignore
        info.context.errors = self.errors
        return _next(root, info, *args, **kwargs)

    def on_execute(self) -> Generator[None, None, None]:
        self.errors.clear()
        yield
        if self.execution_context.result:
            if not self.execution_context.result.errors:
                self.execution_context.result.errors = []
            self.execution_context.result.errors.extend(self.errors)
