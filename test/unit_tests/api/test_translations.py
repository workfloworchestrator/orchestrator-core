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


def test_get_translations_valid_language(test_client):
    response = test_client.get("/api/translations/en-GB")
    assert response.status_code == HTTPStatus.OK
    assert isinstance(response.json(), dict)


def test_get_translations_invalid_language_pattern(test_client):
    response = test_client.get("/api/translations/invalid")
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
