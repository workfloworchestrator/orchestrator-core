# Copyright 2019-2026 SURF.
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


def test_log_error_returns_empty_dict(test_client):
    response = test_client.post("/api/user/error", json={"key": "value", "message": "something went wrong"})
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {}


def test_log_user_info_with_valid_body(test_client):
    response = test_client.post("/api/user/log/testuser", json={"message": "user logged in"})
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {}


def test_log_user_info_with_non_json_body(test_client):
    # A plain dict body that won't yield a "message" key when re-parsed as JSON via str()
    # str({"no_message": "here"}) produces something like "{'no_message': 'here'}" which is
    # not valid JSON, so json_loads will raise and the except branch sets _message = message.
    response = test_client.post("/api/user/log/testuser", json={"no_message": "here"})
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {}
