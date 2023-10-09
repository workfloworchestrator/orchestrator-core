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


from typing import Dict, Iterator, Optional, Annotated

from pydantic import BaseModel, ConfigDict, ValidationInfo, conint, model_validator, Field

from orchestrator.utils.vlans import VlanRanges


class BFD(BaseModel):
    model_config = ConfigDict(json_schema_extra={"format": "optGroup"})

    # order matters, this should be first
    enabled: bool
    minimum_interval: Optional[conint(ge=1, le=255000)] = 900  # type: ignore
    multiplier: Optional[conint(ge=1, le=255)] = 3  # type: ignore

    @model_validator(mode="after")
    def check_optional_fields(cls, info: ValidationInfo) -> Dict:  # noqa: B902
        values = info.data
        if not values.get("enabled"):
            values.pop("minimum_interval", None)
            values.pop("multiplier", None)

        return values


MTU = Annotated[int, Field(ge=1500, le=9000)]


# class MTU(ConstrainedInt):
#     ge = 1500
#     le = 9000
#
#     # TODO pydantic V2 migration
#     # @classmethod
#     # def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
#     #     super().__modify_schema__(field_schema)
#     #     field_schema["multipleOf"] = 7500


class VlanRangesValidator(VlanRanges):
    # TODO pydantic V2 migration (see nwd-api and/or migrate to nwastdlib)

    # @classmethod
    # def __modify_schema__(cls, field_schema: Dict) -> None:
    #     field_schema.update(
    #         pattern="^([1-4][0-9]{0,3}(-[1-4][0-9]{0,3})?,?)+$",
    #         examples=["345", "20-23,45,50-100"],
    #         type="string",
    #         format="vlan",
    #     )

    @classmethod
    def __get_validators__(cls) -> Iterator:
        # one or more validators may be yielded which will be called in the
        # order to validate the input, each validator will receive as an input
        # the value returned from the previous validator
        yield VlanRanges
