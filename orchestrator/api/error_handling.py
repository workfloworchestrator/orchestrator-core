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


from http import HTTPStatus
from typing import Any, NoReturn

from fastapi.exceptions import HTTPException
from starlette.datastructures import MutableHeaders


class ProblemDetailException(HTTPException):
    def __init__(
        self,
        status: int,
        title: str | None = None,
        detail: Any = None,
        headers: dict | None = None,
        error_type: str | None = None,
    ) -> None:
        if headers is None:
            headers = {}

        super().__init__(status_code=status, detail=detail, headers=headers)
        self.title = title
        self.type = error_type


def raise_status(status: int, detail: Any = None, headers: MutableHeaders | dict | None = None) -> NoReturn:
    status = HTTPStatus(status)
    if isinstance(headers, MutableHeaders):
        headers = dict(**headers)
    raise ProblemDetailException(status=status.value, title=status.phrase, detail=detail, headers=headers)
