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
from __future__ import annotations

import warnings

from nwastdlib.vlans import VlanRanges

__all__ = [
    "VlanRanges",
]

warnings.warn(
    "VlanRanges will be removed from orchestrator-core in an upcoming release. "
    "Please import it from nwastdlib (>= 1.5.0) instead.",
    DeprecationWarning,
    stacklevel=1,
)
