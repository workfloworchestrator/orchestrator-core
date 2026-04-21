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

from typing import Any


def get_dict_updates(obj1: dict, obj2: dict) -> dict:
    updated = {}
    for key in obj2:
        if key in obj1:
            if isinstance(obj1[key], dict) and isinstance(obj2[key], dict):
                nested_updates = get_updated_properties(obj1[key], obj2[key])
                if nested_updates:
                    updated[key] = nested_updates
            elif obj1[key] != obj2[key]:
                updated[key] = obj2[key]
        else:
            updated[key] = obj2[key]
    return updated


def get_updated_properties(obj1: Any, obj2: Any) -> Any:
    if isinstance(obj1, dict) and isinstance(obj2, dict):
        return get_dict_updates(obj1, obj2)
    if obj1 != obj2:
        return obj2
    return None
