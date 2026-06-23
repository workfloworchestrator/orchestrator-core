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


from http import HTTPStatus
from uuid import UUID

from orchestrator.core.api.error_handling import raise_status
from orchestrator.core.db import db
from orchestrator.core.db.database import BaseModel as DbBaseModel


def delete(cls: type[DbBaseModel], primary_key: UUID) -> None:
    table = cls.__table__  # type: ignore[attr-defined]
    pk = list({k: v for k, v, *_ in table.columns._collection if v.primary_key}.keys())[0]
    row_count = cls.query.filter(cls.__dict__[pk] == primary_key).delete()
    db.session.commit()
    if row_count > 0:
        return
    raise_status(HTTPStatus.NOT_FOUND)
