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


def remove_redundant_ws(line: str) -> str:
    """Remove redundant white space from a line.

    Redundant being multiple spaces where only one is needed.

    >>> remove_redundant_ws(" a  b  c ")
    'a b c'

    >>> remove_redundant_ws("a b c")
    'a b c'

    >>> remove_redundant_ws("   ")
    ''

    Args:
        line: the string to remove redundant white space from

    Returns:
        Cleaned up string with only one space between textual elements.

    """
    return " ".join(line.split())
