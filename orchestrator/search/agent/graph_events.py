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


class GraphNodeEnterValue(TypedDict):
    """Typed structure for GRAPH_NODE_ENTER event value."""

    node: str
    step_type: str


class GraphNodeEnterEvent(CustomEvent):
    """Event emitted when entering a graph node."""

    name: str = Field(default="GRAPH_NODE_ENTER", frozen=True)
    value: GraphNodeEnterValue


class GraphNodeExitValue(TypedDict):
    """Typed structure for GRAPH_NODE_EXIT event value."""

    node: str
    next_node: str | None


class GraphNodeExitEvent(CustomEvent):
    """Event emitted when exiting a graph node."""

    name: str = Field(default="GRAPH_NODE_EXIT", frozen=True)
    value: GraphNodeExitValue


class TransitionValue(TypedDict):
    """Typed structure for TRANSITION event value."""

    node: str
    to_node: str
    decision: str


class TransitionEvent(CustomEvent):
    """Event emitted when transitioning between graph nodes."""

    name: str = Field(default="TRANSITION", frozen=True)
    value: TransitionValue
