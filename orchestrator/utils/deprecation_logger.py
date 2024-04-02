# Copyright 2019-2024 SURF.
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

from starlette.requests import Request
from structlog import get_logger

logger = get_logger(__name__)


def deprecated_endpoint(request: Request) -> None:
    logger.warning(
        "This function is deprecated. Please use the GraphQL query instead", method=request.method, url=str(request.url)
    )
