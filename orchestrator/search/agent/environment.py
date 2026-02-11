from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

logger = structlog.get_logger(__name__)


class MemoryScope(Enum):
    """Defines what context is visible to different nodes."""

    FULL = "full"  # User questions + answers + execution traces (PlannerNode)
    CONVERSATION = "conversation"  # User questions + answers only (Action nodes)


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
    decision_reason: str | None = None  # For PlannerNode: why this route was chosen

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

    def start_node_step(self, node_step: NodeStep):
        """Start recording a new node execution."""
        if not self.current_turn:
            raise ValueError("No active turn")
        self.current_turn.current_node_step = node_step

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

    def complete_turn(self, assistant_answer: str, query_id: UUID | None = None):
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

            # Execution trace as separate system context (only for FULL scope)
            if scope == MemoryScope.FULL and turn.node_steps:
                # Filter out PlannerNode - only show action nodes with actual work
                action_nodes = [step for step in turn.node_steps if step.step_type != "PlannerNode"]

                if action_nodes:
                    trace_lines = ["Plan executed:"]
                    for i, node_step in enumerate(action_nodes, 1):
                        trace_lines.append(f"  {i}. [Node] {node_step.step_type}")
                        if node_step.tool_steps:
                            for tool_step in node_step.tool_steps:
                                # Add results info if available
                                result_info = f" ({tool_step.results_count} results)" if tool_step.results_count else ""
                                trace_lines.append(
                                    f"     • [Tool] {tool_step.step_type}: {tool_step.description}{result_info}"
                                )
                    # Add trace as system message (not user input)
                    from pydantic_ai.messages import SystemPromptPart

                    messages.append(ModelRequest(parts=[SystemPromptPart(content="\n".join(trace_lines))]))

            # Assistant response
            messages.append(ModelResponse(parts=[TextPart(content=turn.assistant_answer)]))

        # Always add current turn's user question
        if self.current_turn:
            messages.append(ModelRequest(parts=[UserPromptPart(content=self.current_turn.user_question)]))

        return messages

    def format_current_context(self, state) -> str:
        """Format available context from previous runs.

        Shows what's available to use in the current run (results, exports, etc).
        Reads state from SearchState instead of internal tracking.
        """
        if not state.query_id and not state.results_count:
            return "None"

        lines = []

        # Show what's available from previous runs
        if state.results_count and state.results_count > 0:
            count = state.results_count
            entity_type = state.query.entity_type.value if state.query else "records"
            lines.append(f"Results available: {count} {entity_type}")

        if state.export_url:
            lines.append(f"Export ready: {state.export_url}")

        if state.query_id:
            lines.append(f"Query ID: {state.query_id}")

        return "\n".join(lines) if lines else "None"

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

        # Filter out PlannerNode - only show action nodes
        action_nodes = [step for step in all_node_steps if step.step_type != "PlannerNode"]

        if not action_nodes:
            return "None"

        lines = ["Plan executed:"]
        for i, node_step in enumerate(action_nodes, 1):
            lines.append(f"  {i}. [Node] {node_step.step_type}")
            if node_step.tool_steps:
                for tool_step in node_step.tool_steps:
                    result_info = f" ({tool_step.results_count} results)" if tool_step.results_count else ""
                    lines.append(f"     • [Tool] {tool_step.step_type}: {tool_step.description}{result_info}")

        return "\n".join(lines)

    def format_context_for_llm(
        self,
        state,
        *,
        include_available_context: bool = False,
        include_current_run_steps: bool = False,
    ) -> str:
        """Universal context formatter for LLM prompts.

        Provides a single consistent interface for formatting conversation context
        with configurable sections. Current user request and conversation history
        are passed via message_history parameter, not included here.

        Args:
            state: SearchState instance for accessing current context
            include_available_context: Show context from previous runs (query_id, results, etc)
            include_current_run_steps: Show steps executed so far in current run

        Returns:
            Formatted context string ready to insert into prompt
        """
        sections = []

        # Available context from previous runs
        if include_available_context:
            context = self.format_current_context(state)
            sections.append("# Available Context from Previous Runs")
            sections.append(context)

        # Current run steps (for replanning)
        if include_current_run_steps:
            steps = self.format_current_steps()
            if sections:
                sections.append("")
            sections.append("# Steps Already Executed")
            sections.append(steps)

        return "\n".join(sections)
