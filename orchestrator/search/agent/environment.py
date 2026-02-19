from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict
from pydantic_ai.messages import ModelRequest, ModelResponse, SystemPromptPart, TextPart, UserPromptPart

logger = structlog.get_logger(__name__)


class MemoryScope(Enum):
    """Defines what context is visible to different nodes."""

    FULL = "full"  # User questions + answers + full execution traces (PlannerNode)
    LIGHTWEIGHT = "lightweight"  # User questions + answers + full query JSON (Search/Aggregation nodes)
    MINIMAL = "minimal"  # User questions + answers + query_id only (ResultActions node)


@dataclass
class StepRecord:
    """Base class for execution steps in a turn.

    A step represents a discrete action taken during graph execution,
    either visiting a node or calling a tool.
    """

    step_type: str  # Specific type: node name or tool name
    description: str
    step_category: str = ""  # "node" or "tool" - set by subclass
    success: bool = True
    error_message: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class NodeStep(StepRecord):
    """Records a node execution in the graph.

    Contains nested tool_steps that were executed within this node.
    """

    tool_steps: list["ToolStep"] = field(default_factory=list)  # Tools called within this node

    def __post_init__(self):
        self.step_category = "node"

    def add_tool_step(self, tool_step: "ToolStep") -> None:
        """Add a tool step that was executed within this node."""
        self.tool_steps.append(tool_step)


@dataclass
class ToolStep(StepRecord):
    """Records a tool call execution."""

    entity_type: str | None = None
    results_count: int = 0
    query_operation: str | None = None
    query_snapshot: dict | None = None
    query_id: UUID | None = None

    def __post_init__(self):
        self.step_category = "tool"


@dataclass
class CompletedTurn:
    user_question: str
    assistant_answer: str
    node_steps: list[NodeStep]  # Only top-level NodeSteps (which contain ToolSteps)
    timestamp: datetime


@dataclass
class CurrentTurn:
    user_question: str
    node_steps: list[NodeStep] = field(default_factory=list)  # Only top-level NodeSteps
    current_node_step: NodeStep | None = None  # The currently active node
    timestamp: datetime = field(default_factory=lambda: datetime.now())


class ConversationEnvironment(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    completed_turns: list[CompletedTurn] = []
    current_turn: CurrentTurn | None = None
    hidden: dict[str, Any] = {}

    def start_turn(self, user_question: str):
        self.current_turn = CurrentTurn(user_question=user_question, node_steps=[])

    def record_node_entry(self, node_name: str) -> None:
        """Record entering a new node (finishes previous node if any, starts new one)."""
        if not self.current_turn:
            raise ValueError("No active turn")

        if self.current_turn.current_node_step:
            self.finish_node_step()

        self.current_turn.current_node_step = NodeStep(
            step_type=node_name,
            description=f"Executing {node_name}",
        )

    def record_tool_step(self, tool_step: ToolStep):
        """Record a tool call within the current node."""
        if not self.current_turn:
            raise ValueError("No active turn")
        if not self.current_turn.current_node_step:
            raise ValueError("No active node step - must call start_node_step first")

        # Add tool to current node
        self.current_turn.current_node_step.add_tool_step(tool_step)

    def finish_node_step(self):
        """Finish the current node step and add it to the list."""
        if not self.current_turn:
            raise ValueError("No active turn")
        if not self.current_turn.current_node_step:
            raise ValueError("No active node step to finish")

        self.current_turn = CurrentTurn(
            user_question=self.current_turn.user_question,
            node_steps=list(self.current_turn.node_steps) + [self.current_turn.current_node_step],
            current_node_step=None,
            timestamp=self.current_turn.timestamp,
        )

    def complete_turn(self, assistant_answer: str):
        if not self.current_turn:
            raise ValueError("No active turn")

        # Finish any in-progress node step
        if self.current_turn.current_node_step:
            self.finish_node_step()

        logger.debug(
            "complete_turn: before",
            completed_count_before=len(self.completed_turns),
            current_turn_question=self.current_turn.user_question,
            node_step_count=len(self.current_turn.node_steps),
        )

        completed = CompletedTurn(
            user_question=self.current_turn.user_question,
            assistant_answer=assistant_answer,
            node_steps=list(self.current_turn.node_steps),
            timestamp=self.current_turn.timestamp,
        )
        # Force Pydantic to detect change by creating new list
        self.completed_turns.append(completed)
        self.completed_turns = list(self.completed_turns)

        logger.debug(
            "complete_turn: after append",
            completed_count_after=len(self.completed_turns),
            last_completed_question=self.completed_turns[-1].user_question if self.completed_turns else None,
        )

        self.current_turn = None

    def _format_query_summary(self, node_steps: list[NodeStep], include_full_query: bool = True) -> str | None:
        """Format query summary - either full JSON or just query_id with one-liner.

        Args:
            node_steps: List of NodeStep objects to extract queries from
            include_full_query: If True, show full query JSON; if False, just query_id + description

        Returns:
            Formatted query summary string, or None if no queries
        """
        import json

        # Find tool steps with query_ids
        query_tools = []
        for node_step in node_steps:
            for tool_step in node_step.tool_steps:
                if tool_step.query_id:
                    query_tools.append(tool_step)

        if not query_tools:
            return None

        summaries = []
        for tool in query_tools:
            if include_full_query and tool.query_snapshot:
                # Full query JSON for Search/Aggregation nodes
                query_json = json.dumps(tool.query_snapshot, indent=2)
                summaries.append(f"Query {tool.query_id}:\n{query_json}")
            else:
                # Minimal one-liner for ResultActions node
                operation = tool.query_operation or "QUERY"
                entity = tool.entity_type or "unknown"
                results = f" ({tool.results_count} results)" if tool.results_count else ""
                summaries.append(f"Query {tool.query_id}: {operation} {entity}{results}")

        return "\n\n".join(summaries) if summaries else None

    def _format_execution_trace(self, node_steps: list[NodeStep]) -> str | None:
        """Format node steps as execution trace string.

        Args:
            node_steps: List of NodeStep objects to format

        Returns:
            Formatted execution trace string, or None if no action nodes
        """
        # Filter out PlannerNode - only show action nodes
        action_nodes = [step for step in node_steps if step.step_type != "PlannerNode"]

        if not action_nodes:
            return None

        lines = ["Plan executed:"]
        for i, node_step in enumerate(action_nodes, 1):
            lines.append(f"  {i}. [Node] {node_step.step_type}")
            if node_step.tool_steps:
                for tool_step in node_step.tool_steps:
                    result_info = f" ({tool_step.results_count} results)" if tool_step.results_count else ""
                    query_info = f" [query: {tool_step.query_id}]" if tool_step.query_id else ""
                    lines.append(f"     • [Tool] {tool_step.step_type}: {tool_step.description}{result_info}{query_info}")

        return "\n".join(lines)

    def get_message_history(
        self, max_turns: int = 5, scope: MemoryScope = MemoryScope.FULL
    ) -> list[ModelRequest | ModelResponse]:
        """Get conversation history as pydantic-ai message objects for message_history parameter.

        Args:
            max_turns: Maximum number of recent turns to include
            scope: Memory scope controlling what details to include

        Returns:
            List of ModelRequest/ModelResponse messages for agent message_history
        """
        recent = self.completed_turns[-max_turns:]

        # Build messages using pydantic-ai message types
        messages = []
        for turn in recent:
            # User message
            messages.append(ModelRequest(parts=[UserPromptPart(content=turn.user_question)]))

            # Add context based on scope
            if turn.node_steps:
                if scope == MemoryScope.FULL:
                    # Full execution trace with all details
                    trace = self._format_execution_trace(turn.node_steps)
                    if trace:
                        messages.append(ModelRequest(parts=[SystemPromptPart(content=trace)]))
                elif scope == MemoryScope.LIGHTWEIGHT:
                    # Full query JSON for re-running
                    summary = self._format_query_summary(turn.node_steps, include_full_query=True)
                    if summary:
                        messages.append(ModelRequest(parts=[SystemPromptPart(content=summary)]))
                elif scope == MemoryScope.MINIMAL:
                    # Just query_id + one-liner
                    summary = self._format_query_summary(turn.node_steps, include_full_query=False)
                    if summary:
                        messages.append(ModelRequest(parts=[SystemPromptPart(content=summary)]))

            # Assistant response
            messages.append(ModelResponse(parts=[TextPart(content=turn.assistant_answer)]))

        # Always add current turn's user question
        if self.current_turn:
            messages.append(ModelRequest(parts=[UserPromptPart(content=self.current_turn.user_question)]))

        return messages

    def format_current_steps(self) -> str:
        """Format the steps taken in the current turn for display in prompts.

        Used for replanning to show what has been executed so far in this incomplete turn.
        Uses the same format as message history for consistency.
        """
        if not self.current_turn:
            return "None"

        all_node_steps = list(self.current_turn.node_steps)
        if self.current_turn.current_node_step:
            all_node_steps.append(self.current_turn.current_node_step)

        trace = self._format_execution_trace(all_node_steps)
        return trace if trace else "None"

    def format_context_for_llm(
        self,
        state,
        *,
        include_current_run_steps: bool = False,
    ) -> str:
        """Universal context formatter for LLM prompts.

        Provides a single consistent interface for formatting conversation context
        with configurable sections. Current user request and conversation history
        are passed via message_history parameter, not included here.

        Args:
            state: SearchState instance for accessing current context
            include_current_run_steps: Show steps executed so far in current run

        Returns:
            Formatted context string ready to insert into prompt
        """
        # Current run steps (for replanning)
        if include_current_run_steps:
            steps = self.format_current_steps()
            return f"# Steps Already Executed\n{steps}"

        return ""
