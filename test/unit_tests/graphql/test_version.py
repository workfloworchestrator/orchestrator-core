# Copyright 2019-2026 ESnet, GÉANT, SURF.
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

import json
from http import HTTPStatus

from test.unit_tests.config import GRAPHQL_ENDPOINT


def get_version_query() -> bytes:
    query = """
        query VersionQuery {
        version {
            applicationVersions
        }
        }
    """
    return json.dumps({"operationName": "VersionQuery", "query": query}).encode("utf-8")


def test_version_query(test_client_graphql):
    data = get_version_query()
    response = test_client_graphql.post(GRAPHQL_ENDPOINT, content=data, headers={"Content-Type": "application/json"})
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "errors" not in result
