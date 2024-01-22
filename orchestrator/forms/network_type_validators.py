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


from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator


class BFD(BaseModel):
    model_config = ConfigDict(json_schema_extra={"format": "optGroup"})

    # order matters, this should be first
    enabled: bool
    minimum_interval: Annotated[int, Field(ge=1, le=255000)] | None = 900
    multiplier: Annotated[int, Field(ge=1, le=255)] | None = 3

    @model_validator(mode="after")
    def check_optional_fields(self) -> "BFD":
        if not self.enabled:
            self.minimum_interval = None
            self.multiplier = None

        return self

    @model_serializer
    def bfd_serializer(self) -> dict[str, Any]:
        if not self.enabled:
            # If BFD is disabled the interval and multiplier are None. We need to exclude them from
            # the output to prevent overriding their default values in the form
            return {"enabled": self.enabled}

        return {"enabled": self.enabled, "minimum_interval": self.minimum_interval, "multiplier": self.multiplier}


MTU = Annotated[int, Field(ge=1500, le=9000, json_schema_extra={"multipleOf": 7500})]
