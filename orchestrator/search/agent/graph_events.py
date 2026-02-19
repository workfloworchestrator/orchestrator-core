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


from dataclasses import dataclass
from typing import Callable

from ag_ui.core import BaseEvent, CustomEvent
from pydantic import Field
from typing_extensions import TypedDict

from orchestrator.search.agent.utils import current_timestamp_ms


class GraphNodeActiveValue(TypedDict, total=False):
    """Typed structure for GRAPH_NODE_ACTIVE event value."""

    node: str
    reasoning: str


class GraphNodeActiveEvent(CustomEvent):
    """Event emitted when a graph node becomes active."""

    name: str = Field(default="GRAPH_NODE_ACTIVE", frozen=True)
    value: GraphNodeActiveValue


@dataclass
class GraphDeps:
    """Request-scoped dependencies injected into graph nodes via ctx.deps."""

    _emit: Callable[[BaseEvent], None]

    def emit_node_active(self, node_name: str, reasoning: str | None = None) -> None:
        """Emit a GRAPH_NODE_ACTIVE event via the attached emitter."""
        value = GraphNodeActiveValue(node=node_name)
        if reasoning:
            value["reasoning"] = reasoning
        self._emit(GraphNodeActiveEvent(timestamp=current_timestamp_ms(), value=value))
