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
from unittest import mock

from sqlalchemy.exc import OperationalError


def test_get_health(test_client):
    response = test_client.get("/api/health/")
    assert HTTPStatus.OK == response.status_code
    assert response.json() == "OK"


@mock.patch("orchestrator.db.db.session")
def test_get_health_no_connection(mock_session, test_client):
    mock_session.execute.side_effect = OperationalError("THIS", "IS", "KABOOM")
    response = test_client.get("/api/health/")
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
