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
from unittest import mock

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession


def test_get_health(test_client):
    response = test_client.get("/api/health/")
    assert HTTPStatus.OK == response.status_code
    assert response.json() == "OK"


def test_get_health_no_connection(test_client):
    with mock.patch.object(AsyncSession, "execute", side_effect=OperationalError("THIS", "IS", "KABOOM")):
        response = test_client.get("/api/health/")
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
