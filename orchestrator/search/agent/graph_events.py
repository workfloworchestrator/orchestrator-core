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


from ag_ui.core import CustomEvent
from pydantic import Field
from typing_extensions import TypedDict


class GraphNodeActiveValue(TypedDict, total=False):
    """Typed structure for GRAPH_NODE_ACTIVE event value."""

    node: str
    step_type: str
    reasoning: str


class GraphNodeActiveEvent(CustomEvent):
    """Event emitted when a graph node becomes active."""

    name: str = Field(default="GRAPH_NODE_ACTIVE", frozen=True)
    value: GraphNodeActiveValue
