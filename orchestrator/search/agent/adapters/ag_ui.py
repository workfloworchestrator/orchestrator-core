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

"""Custom AG-UI transport layer.

Two responsibilities:
1. Replace full query results with lightweight QueryArtifact references for the frontend
2. Pass through CustomEvent instances (e.g. AGENT_STEP_ACTIVE) that pydantic-ai's
   default handle_event() would silently drop via its catch-all `case _: pass`
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from ag_ui.core import BaseEvent, CustomEvent, EventType, ToolCallResultEvent
from pydantic_ai.messages import FunctionToolResultEvent, ToolReturnPart
from pydantic_ai.ui import NativeEvent
from pydantic_ai.ui.ag_ui import AGUIAdapter, AGUIEventStream

from orchestrator.search.query.results import QueryArtifact


@dataclass
class ArtifactEventStream(AGUIEventStream[Any, Any]):
    """Custom event stream for the search agent.

    - Replaces tool results that carry QueryArtifact metadata with the artifact JSON,
      so the AG-UI frontend receives a lightweight reference instead of full data.
    - Yields CustomEvent instances (AGENT_STEP_ACTIVE) that the base class would drop.
    """

    async def handle_event(self, event: NativeEvent) -> AsyncIterator[BaseEvent]:
        # Pass through AG-UI CustomEvents (e.g. AGENT_STEP_ACTIVE) that the
        # base class match/case would silently discard.
        if isinstance(event, CustomEvent):
            yield event
            return

        async for e in super().handle_event(event):
            yield e

    async def handle_function_tool_result(self, event: FunctionToolResultEvent) -> AsyncIterator[BaseEvent]:
        result = event.result
        if isinstance(result, ToolReturnPart) and isinstance(result.metadata, QueryArtifact):
            yield ToolCallResultEvent(
                message_id=self.new_message_id(),
                type=EventType.TOOL_CALL_RESULT,
                role="tool",
                tool_call_id=result.tool_call_id,
                content=result.metadata.model_dump_json(),
            )
            return

        # Default behavior for all other tools
        async for e in super().handle_function_tool_result(event):
            yield e


class ArtifactAGUIAdapter(AGUIAdapter[Any, Any]):
    """AGUIAdapter that uses ArtifactEventStream."""

    def build_event_stream(self) -> ArtifactEventStream:
        return ArtifactEventStream(self.run_input, accept=self.accept)
