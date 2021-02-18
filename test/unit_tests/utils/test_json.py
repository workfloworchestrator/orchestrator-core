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

import re
from datetime import datetime, timezone

from orchestrator.utils.datetime import nowtz
from orchestrator.utils.json import json_dumps, json_loads


def test_serialization_datetime():
    json_str = json_dumps({"end_date": nowtz()})
    assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", json_str)


def test_deserialization_datetime():
    json_str = '{"end_date": "2019-12-06T19:25:22+00:00"}'
    dct = json_loads(json_str)
    assert "end_date" in dct
    assert dct["end_date"] == datetime(2019, 12, 6, 19, 25, 22, 0, timezone.utc)

    dct = {"end_date": datetime(2019, 12, 6, 19, 25, 22, 0, timezone.utc)}
    assert json_loads(json_dumps(dct)) == dct
