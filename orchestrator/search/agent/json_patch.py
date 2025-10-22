# Copyright 2019-2025 SURF, GÉANT.
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

from typing import Any, Literal

from pydantic import BaseModel, Field


class JSONPatchOp(BaseModel):
    """A JSON Patch operation (RFC 6902).

    Docs reference: https://docs.ag-ui.com/concepts/state
    """

    op: Literal["add", "remove", "replace", "move", "copy", "test"] = Field(
        description="The operation to perform: add, remove, replace, move, copy, or test"
    )
    path: str = Field(description="JSON Pointer (RFC 6901) to the target location")
    value: Any | None = Field(
        default=None,
        description="The value to apply (for add, replace operations)",
    )
    from_: str | None = Field(
        default=None,
        alias="from",
        description="Source path (for move, copy operations)",
    )

    @classmethod
    def upsert(cls, path: str, value: Any, existed: bool) -> "JSONPatchOp":
        """Create an add or replace operation depending on whether the path existed.

        Args:
            path: JSON Pointer path to the target location
            value: The value to set
            existed: True if the path already exists (use replace), False otherwise (use add)

        Returns:
            JSONPatchOp with 'replace' if existed is True, 'add' otherwise
        """
        return cls(op="replace" if existed else "add", path=path, value=value)
