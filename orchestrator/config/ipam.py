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


class IpamStates:
    FREE = 0
    ALLOCATED = 1
    EXPIRED = 2
    PLANNED = 3
    RESERVED = 4
    SUSPEND = 5
    FAILED = 6  # front end code only
    ALLOCATED_SUBNET = 7  # only needed for color coding in frontend

    TRANS = {
        FREE: "Vrij",
        ALLOCATED: "Gealloceerd",
        EXPIRED: "Verlopen",
        PLANNED: "Gepland",
        RESERVED: "Gereserveerd",
        SUSPEND: "Nonactief",
        ALLOCATED_SUBNET: "Gealloceerd subnet",
    }

    @classmethod
    def nl(cls, state: int) -> str:
        return cls.TRANS[state]
