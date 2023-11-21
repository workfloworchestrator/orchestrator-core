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


from typing import Any, Dict, Iterator, Optional

from pydantic import BaseModel, ConfigDict, ConstrainedInt, Field, model_validator
from typing_extensions import Annotated

from orchestrator.utils.vlans import VlanRanges


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


class MTU(ConstrainedInt):
    ge = 1500
    le = 9000

    @classmethod
    # TODO[pydantic]: We couldn't refactor `__modify_schema__`, please create the `__get_pydantic_json_schema__` manually.
    # Check https://docs.pydantic.dev/latest/migration/#defining-custom-types for more information.
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        super().__modify_schema__(field_schema)
        field_schema["multipleOf"] = 7500


class VlanRangesValidator(VlanRanges):
    @classmethod
    # TODO[pydantic]: We couldn't refactor `__modify_schema__`, please create the `__get_pydantic_json_schema__` manually.
    # Check https://docs.pydantic.dev/latest/migration/#defining-custom-types for more information.
    def __modify_schema__(cls, field_schema: Dict) -> None:
        field_schema.update(
            pattern="^([1-4][0-9]{0,3}(-[1-4][0-9]{0,3})?,?)+$",
            examples=["345", "20-23,45,50-100"],
            type="string",
            format="vlan",
        )

    @classmethod
    # TODO[pydantic]: We couldn't refactor `__get_validators__`, please create the `__get_pydantic_core_schema__` manually.
    # Check https://docs.pydantic.dev/latest/migration/#defining-custom-types for more information.
    def __get_validators__(cls) -> Iterator:
        # one or more validators may be yielded which will be called in the
        # order to validate the input, each validator will receive as an input
        # the value returned from the previous validator
        yield VlanRanges
