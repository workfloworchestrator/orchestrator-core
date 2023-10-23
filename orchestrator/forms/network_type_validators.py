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


from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, WrapSerializer, model_validator
from typing_extensions import Annotated

from nwastdlib.vlans import VlanRanges


class BFD(BaseModel):
    model_config = ConfigDict(json_schema_extra={"format": "optGroup"})

    # order matters, this should be first
    enabled: bool
    minimum_interval: Optional[Annotated[int, Field(ge=1, le=255000)]] = 900  # type: ignore
    multiplier: Optional[Annotated[int, Field(ge=1, le=255)]] = 3  # type: ignore

    @model_validator()
    @classmethod
    def check_optional_fields(cls, values: Dict) -> Dict:  # noqa: B902
        if not values.get("enabled"):
            values.pop("minimum_interval", None)
            values.pop("multiplier", None)

        return values


MTU = Annotated[int, Field(ge=1500, le=9000, json_schema_extra={"multipleOf": 7500})]


def _serialize_vlanranges(_unused: Any, _handler: SerializerFunctionWrapHandler) -> dict:
    return {
        "pattern": "^([1-4][0-9]{0,3}(-[1-4][0-9]{0,3})?,?)+$",
        "examples": ["345", "20-23,45,50-100"],
        "type": "string",
        "format": "vlanrange",
    }


# TODO Make sure this serializes to str, previously had `ENCODERS_BY_TYPE[VlanRanges]=str`
VlanRangesValidator = Annotated[VlanRanges, WrapSerializer(_serialize_vlanranges)]
