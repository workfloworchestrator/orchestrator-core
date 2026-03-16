"""Mock event factories for adapter output tests.

These factories produce the same event types that `agent.run_stream_events()`
yields, so adapter tests can exercise transformation logic without any LLM or
DB calls.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest
from ag_ui.core import RunAgentInput, UserMessage
from pydantic_ai.messages import FunctionToolResultEvent, ToolReturnPart
from pydantic_ai.run import AgentRunResult, AgentRunResultEvent

from orchestrator.search.agent.artifacts import ToolArtifact
from orchestrator.search.agent.events import AgentStepActiveEvent, AgentStepActiveValue
from orchestrator.search.agent.utils import current_timestamp_ms

pytestmark = pytest.mark.search


def pytest_ignore_collect(collection_path, config):  # noqa: ARG001
    """Skip agent tests when AGENT_ENABLED is false (deps won't be installed)."""
    from orchestrator.llm_settings import llm_settings

    if not llm_settings.AGENT_ENABLED:
        return True
    return False


def make_artifact_event(
    tool_name: str,
    artifact: ToolArtifact,
    content: Any | None = None,
    tool_call_id: str = "tc_1",
) -> FunctionToolResultEvent:
    """FunctionToolResultEvent whose ToolReturnPart carries a ToolArtifact.

    Content defaults to the artifact's JSON representation — matching what
    real tools return via ToolReturn(metadata=..., content=artifact.model_dump_json()).
    """
    if content is None:
        content = artifact.model_dump_json()
    part = ToolReturnPart(
        tool_name=tool_name,
        content=content,
        tool_call_id=tool_call_id,
        metadata=artifact,
    )
    return FunctionToolResultEvent(result=part)


def make_non_artifact_event(
    tool_name: str,
    content: Any = "plain result",
    tool_call_id: str = "tc_2",
) -> FunctionToolResultEvent:
    """FunctionToolResultEvent without ToolArtifact metadata."""
    part = ToolReturnPart(
        tool_name=tool_name,
        content=content,
        tool_call_id=tool_call_id,
    )
    return FunctionToolResultEvent(result=part)


def make_text_result_event(text: str = "Execution completed") -> AgentRunResultEvent[str]:
    """AgentRunResultEvent with a text output."""
    return AgentRunResultEvent(result=AgentRunResult(output=text))


def make_step_event(step_name: str, reasoning: str | None = None) -> AgentStepActiveEvent:
    """AGENT_STEP_ACTIVE custom event."""
    value = AgentStepActiveValue(step=step_name)
    if reasoning:
        value["reasoning"] = reasoning
    return AgentStepActiveEvent(timestamp=current_timestamp_ms(), value=value)


def minimal_run_input() -> RunAgentInput:
    """Minimal AG-UI RunAgentInput for testing."""
    return RunAgentInput(
        thread_id="t1",
        run_id="r1",
        state={},
        messages=[UserMessage(id="m1", role="user", content="show subs")],
        tools=[],
        context=[],
        forwarded_props={},
    )


async def mock_event_stream(*events: Any) -> AsyncIterator[Any]:
    """Async generator that yields the given events in order."""
    for event in events:
        yield event
