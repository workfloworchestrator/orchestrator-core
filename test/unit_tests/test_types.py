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

from typing import Union

from orchestrator.core.types import is_of_type


def test_is_of_type():
    """Some tests to see type checks are valid."""
    assert is_of_type(int, Union[int, str])
    assert is_of_type(int, Union[str, int])
    assert is_of_type(str, Union[int, str])
    assert is_of_type(str, Union[str, int])
    assert is_of_type(list[str], Union[str, int]) is False
