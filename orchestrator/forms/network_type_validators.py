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


from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Annotated


class BFD(BaseModel):
    model_config = ConfigDict(json_schema_extra={"format": "optGroup"})

    # order matters, this should be first
    enabled: bool
    minimum_interval: Optional[Annotated[int, Field(ge=1, le=255000)]] = 900
    multiplier: Optional[Annotated[int, Field(ge=1, le=255)]] = 3

    @model_validator(mode="after")
    def check_optional_fields(self) -> "BFD":
        if not self.enabled:
            self.minimum_interval = None
            self.multiplier = None

        return self


MTU = Annotated[int, Field(ge=1500, le=9000, json_schema_extra={"multipleOf": 7500})]
