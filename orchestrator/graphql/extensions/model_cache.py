# Copyright 2022-2025 SURF.
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
from collections.abc import Iterator

from strawberry.extensions import SchemaExtension

from orchestrator.domain.context_cache import cache_subscription_models


class ModelCacheExtension(SchemaExtension):
    """Wraps the GraphQL operation in a cache_subscription_models context.

    For more background, please refer to the documentation of the contextmanager.
    """

    def on_operation(self, *args, **kwargs) -> Iterator[None]:  # type: ignore

        with cache_subscription_models():
            yield
