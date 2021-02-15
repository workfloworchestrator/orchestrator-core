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

from typing import Dict, List

SPEED_TO_INTERFACE_TYPE: Dict[int, List[str]] = {
    1000: ["1000BASE-T", "1000BASE-EX", "1000BASE-LX", "1000BASE-SX", "1000BASE-ZX", "1000BASE-CWDM"],
    10000: ["10GBASE-ER", "10GBASE-LR", "10GBASE-SR", "10GBASE-ZR", "10GBASE-CWDM"],
    40000: ["40GBASE-LR4", "40GBASE-SR4", "40GBASE-CWDM"],
    100000: ["100GBASE-LR4", "100GBASE-SR4", "100GBASE-LR10", "100GBASE-SR10", "100GBASE-CWDM4"],
}

INTERFACE_TYPE_TO_SPEED: Dict[str, int] = {
    ieee_type: speed for speed, ieee_types in SPEED_TO_INTERFACE_TYPE.items() for ieee_type in ieee_types
}


SPEED_TO_IMS_SPEED: Dict[int, str] = {
    1000: "1G",
    10000: "10G",
    40000: "40G",
    100000: "100G",
}
