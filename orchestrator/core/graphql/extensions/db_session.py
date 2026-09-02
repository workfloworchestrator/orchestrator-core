# Copyright 2022-2026 SURF, GÉANT.
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
from collections.abc import AsyncIterator

from strawberry.extensions import SchemaExtension

from orchestrator.core.db import db


class DbSessionExtension(SchemaExtension):
    """Opens a single AsyncSession for the lifetime of a GraphQL operation.

    Exposes it via ``info.context.session`` so resolvers don't each need to open their own
    ``db.async_session()`` block.
    """

    async def on_operation(self) -> AsyncIterator[None]:
        async with db.async_session() as session:
            self.execution_context.context.session = session
            yield
