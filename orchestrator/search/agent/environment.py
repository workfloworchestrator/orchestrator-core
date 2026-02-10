from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict

logger = structlog.get_logger(__name__)


class MemoryScope(Enum):
    """Defines what context is visible to different nodes."""

    FULL = "full"  # User questions + answers + execution traces (IntentNode)
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
    decision_reason: str | None = None  # For IntentNode: why this route was chosen

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


@dataclass
class CurrentContext:
    last_step: StepRecord | None = None
    query_id: UUID | None = None
    results_available: bool = False
    export_url: str | None = None


class ConversationEnvironment(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    completed_turns: list[CompletedTurn] = []
    current_turn: CurrentTurn | None = None
    current_context: CurrentContext = CurrentContext()
    hidden: dict[str, Any] = {}

    def start_turn(self, user_question: str):
        self.current_turn = CurrentTurn(user_question=user_question, node_steps=[])
        # Preserve context from previous turn (query_id, results_available, etc.)
        # Only reset last_step since we're starting fresh steps for this turn
        self.current_context = CurrentContext(
            last_step=None,
            query_id=self.current_context.query_id,
            results_available=self.current_context.results_available,
            export_url=self.current_context.export_url,
        )

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

        # Update context based on tool results
        self.current_context = CurrentContext(
            last_step=tool_step,
            query_id=self.current_context.query_id,
            results_available=(
                tool_step.results_count > 0
                if tool_step.step_type in ("run_search", "run_aggregation")
                else self.current_context.results_available
            ),
            export_url=self.current_context.export_url,
        )

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

        if query_id:
            self.current_context = CurrentContext(
                last_step=self.current_context.last_step,
                query_id=query_id,
                results_available=self.current_context.results_available,
                export_url=self.current_context.export_url,
            )
        self.current_turn = None

    def format_for_llm(self, max_turns: int = 5, scope: MemoryScope = MemoryScope.FULL) -> str:
        """Format conversation history for LLM with configurable scope.

        Args:
            max_turns: Maximum number of recent turns to include
            scope: Memory scope controlling what details to include

        Returns:
            Formatted conversation string
        """
        recent = self.completed_turns[-max_turns:]
        if not recent:
            return "[No previous conversation]"
        sections = []
        for turn in recent:
            sections.append(f"user: {turn.user_question}")

            # Only include execution traces if FULL scope
            if scope == MemoryScope.FULL and turn.node_steps:
                sections.append("Execution trace:")
                for i, node_step in enumerate(turn.node_steps, 1):
                    sections.append(f"  {i}. {node_step.step_type}")
                    if node_step.tool_steps:
                        for tool_step in node_step.tool_steps:
                            # Add results info if available
                            result_info = f" ({tool_step.results_count} results)" if tool_step.results_count else ""
                            sections.append(f"     • {tool_step.step_type}: {tool_step.description}{result_info}")

            sections.append(f"assistant: {turn.assistant_answer}")
        return "\n".join(sections)

    def format_current_context(self) -> str:
        """Format available context from previous runs.

        Shows what's available to use in the current run (results, exports, etc).
        """
        if not self.current_context.query_id and not self.current_context.results_available:
            return "None"

        lines = []

        # Show what's available from previous runs
        if self.current_context.results_available:
            if self.current_context.last_step and isinstance(self.current_context.last_step, ToolStep):
                count = self.current_context.last_step.results_count
                entity_type = self.current_context.last_step.entity_type or "records"
                lines.append(f"Results available: {count} {entity_type}")
            else:
                lines.append("Results available from previous query")

        if self.current_context.export_url:
            lines.append(f"Export ready: {self.current_context.export_url}")

        if self.current_context.query_id:
            lines.append(f"Query ID: {self.current_context.query_id}")

        return "\n".join(lines) if lines else "None"

    def format_current_steps(self) -> str:
        """Format the steps taken in the current turn for display in prompts.

        Used in IntentNode to show what has been executed so far in this graph run.
        """
        if not self.current_turn:
            return "None"

        all_node_steps = list(self.current_turn.node_steps)
        if self.current_turn.current_node_step:
            all_node_steps.append(self.current_turn.current_node_step)

        if not all_node_steps:
            return "None"

        lines = []
        for i, node_step in enumerate(all_node_steps, 1):
            if node_step.decision_reason:
                lines.append(f"{i}. {node_step.step_type}: {node_step.decision_reason}")
            else:
                lines.append(f"{i}. {node_step.step_type}")
            if node_step.tool_steps:
                for tool_step in node_step.tool_steps:
                    result_info = f" ({tool_step.results_count} results)" if tool_step.results_count else ""

                    # Show query snapshot if available (for search/aggregation tools)
                    args_display = ""
                    if tool_step.query_snapshot:
                        import json

                        args_display = f"\n     Query: {json.dumps(tool_step.query_snapshot, indent=2)}"

                    lines.append(f"   • {tool_step.step_type}: {tool_step.description}{result_info}{args_display}")

        return "\n".join(lines)

    def format_context_for_llm(
        self,
        *,
        include_past_conversations: bool = True,
        include_available_context: bool = False,
        include_current_run_steps: bool = False,
        max_past_turns: int = 5,
        memory_scope: MemoryScope = MemoryScope.FULL,
    ) -> str:
        """Universal context formatter for LLM prompts.

        Provides a single consistent interface for formatting conversation context
        with configurable sections. Labels are hardcoded for consistency across all prompts.

        Uses the current turn's user_question which is already tracked in the environment.

        Args:
            include_past_conversations: Show completed conversation turns
            include_available_context: Show context from previous runs (query_id, results, etc)
            include_current_run_steps: Show steps executed so far in current run
            max_past_turns: Maximum number of past turns to include
            memory_scope: Memory scope controlling detail level (FULL includes execution traces, CONVERSATION omits them)

        Returns:
            Formatted context string ready to insert into prompt
        """
        # Get user input from current turn
        user_input = self.current_turn.user_question if self.current_turn else ""

        sections = []

        # Past conversations
        if include_past_conversations:
            conversation = self.format_for_llm(max_turns=max_past_turns, scope=memory_scope)
            sections.append("# Recent Conversation")
            sections.append(conversation)
            sections.append("")

        # Available context from previous runs
        if include_available_context:
            context = self.format_current_context()
            sections.append("# Available Context from Previous Runs")
            sections.append(context)
            sections.append("")

        # Current run
        if include_current_run_steps:
            steps = self.format_current_steps()
            sections.append("# Current Request")
            sections.append(f'"{user_input}"')
            sections.append("")
            sections.append("Steps already executed for this request:")
            sections.append(steps)
        else:
            # Just show current request
            sections.append("# Current Request")
            sections.append(f'"{user_input}"')

        return "\n".join(sections)
