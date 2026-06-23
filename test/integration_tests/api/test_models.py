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

"""Tests for API model helpers: delete (row deletion by primary key)."""

from http import HTTPStatus
from uuid import uuid4

import pytest

from orchestrator.core.api.error_handling import ProblemDetailException
from orchestrator.core.api.models import delete
from orchestrator.core.db import ResourceTypeTable


def test_delete_raises_not_found_for_missing_row(generic_resource_type_1) -> None:
    with pytest.raises(ProblemDetailException) as exc_info:
        delete(ResourceTypeTable, uuid4())
    assert exc_info.value.status_code == HTTPStatus.NOT_FOUND


def test_delete_succeeds_for_existing_row(generic_resource_type_1) -> None:
    delete(ResourceTypeTable, generic_resource_type_1.resource_type_id)
