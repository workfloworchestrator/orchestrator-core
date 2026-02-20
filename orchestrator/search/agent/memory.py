from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict
from pydantic_ai.messages import ModelRequest, ModelResponse, SystemPromptPart, TextPart, UserPromptPart

logger = structlog.get_logger(__name__)


class MemoryScope(Enum):
    """Defines what context is visible to different steps."""

    FULL = "full"  # User questions + answers + full execution traces (Planner)
    LIGHTWEIGHT = "lightweight"  # User questions + answers + full query JSON (Search/Aggregation)
    MINIMAL = "minimal"  # User questions + answers + query_id only (Result Actions)


@dataclass
class Step:
    """Base class for execution steps in a turn.

    A step represents a discrete action taken during agent execution,
    either visiting a node or calling a tool.
    """

    step_type: str  # Specific type: step name or tool name
    description: str
    success: bool = True
    error_message: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class AgentStep(Step):
    """Records an agent step execution.

    Contains nested tool_steps that were executed within this step.
    """

    tool_steps: list["ToolStep"] = field(default_factory=list)  # Tools called by this agent.

    def add_tool_step(self, tool_step: "ToolStep") -> None:
        """Add a tool step that was executed within this step."""
        self.tool_steps.append(tool_step)


@dataclass
class ToolStep(Step):
    """Records a tool call execution."""

    context: dict[str, Any] | None = None


@dataclass
class Turn:
    user_question: str
    assistant_answer: str | None = None
    steps: list[AgentStep] = field(default_factory=list)
    current_step: AgentStep | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now())

    @property
    def is_complete(self) -> bool:
        return self.assistant_answer is not None


class Memory(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    turns: list[Turn] = []

    @property
    def current_turn(self) -> Turn | None:
        """Return the last turn if it's incomplete, else None."""
        if self.turns and not self.turns[-1].is_complete:
            return self.turns[-1]
        return None

    @property
    def completed_turns(self) -> list[Turn]:
        """Return all completed turns."""
        return [t for t in self.turns if t.is_complete]

    def start_turn(self, user_question: str):
        self.turns.append(Turn(user_question=user_question))

    def start_step(self, step_name: str) -> None:
        """Start a new agent step (finishes previous step if any)."""
        if not self.current_turn:
            raise ValueError("No active turn")

        if self.current_turn.current_step:
            self.finish_step()

        self.current_turn.current_step = AgentStep(
            step_type=step_name,
            description=f"Executing {step_name}",
        )

    def record_tool_step(self, tool_step: ToolStep):
        """Record a tool call within the current step."""
        if not self.current_turn:
            raise ValueError("No active turn")
        if not self.current_turn.current_step:
            raise ValueError("No active step — must call start_step first")

        self.current_turn.current_step.add_tool_step(tool_step)

    def finish_step(self):
        """Finish the current step and add it to the list."""
        if not self.current_turn:
            raise ValueError("No active turn")
        if not self.current_turn.current_step:
            raise ValueError("No active step to finish")

        turn = self.current_turn
        if turn.current_step is not None:
            turn.steps.append(turn.current_step)
            turn.current_step = None

    def complete_turn(self, assistant_answer: str):
        if not self.current_turn:
            raise ValueError("No active turn")

        # Finish any in-progress step
        if self.current_turn.current_step:
            self.finish_step()

        turn = self.current_turn

        logger.debug(
            "complete_turn",
            completed_count_before=len(self.completed_turns),
            question=turn.user_question,
            step_count=len(turn.steps),
        )

        turn.assistant_answer = assistant_answer

    def _format_query_summary(self, steps: list[AgentStep], include_full_query: bool = True) -> str | None:
        """Format query summary - either full JSON or just query_id with one-liner.

        Args:
            steps: List of AgentStep objects to extract queries from
            include_full_query: If True, show full query JSON; if False, just query_id + description

        Returns:
            Formatted query summary string, or None if no queries
        """
        import json

        # Find tool steps with query_ids
        query_tools = []
        for step in steps:
            for tool_step in step.tool_steps:
                if tool_step.context and tool_step.context.get("query_id"):
                    query_tools.append(tool_step)

        if not query_tools:
            return None

        summaries = []
        for tool in query_tools:
            query_id = tool.context.get("query_id")
            query_snapshot = tool.context.get("query_snapshot")
            if include_full_query and query_snapshot:
                # Full query JSON for Search/Aggregation nodes
                query_json = json.dumps(query_snapshot, indent=2)
                summaries.append(f"Query {query_id}:\n{query_json}")
            else:
                # Minimal one-liner for ResultActions
                summaries.append(f"Query {query_id}: {tool.description}")

        return "\n\n".join(summaries) if summaries else None

    def _format_execution_trace(self, steps: list[AgentStep]) -> str | None:
        """Format steps as execution trace string.

        Args:
            steps: List of AgentStep objects to format

        Returns:
            Formatted execution trace string, or None if no action steps
        """
        # Filter out Planner - only show action steps
        action_steps = [step for step in steps if step.step_type != "Planner"]

        if not action_steps:
            return None

        lines = ["Plan executed:"]
        for i, step in enumerate(action_steps, 1):
            lines.append(f"  {i}. [Step] {step.step_type}")
            if step.tool_steps:
                for tool_step in step.tool_steps:
                    query_id = tool_step.context.get("query_id") if tool_step.context else None
                    query_info = f" [query: {query_id}]" if query_id else ""
                    lines.append(f"     • [Tool] {tool_step.step_type}: {tool_step.description}{query_info}")

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
            if turn.steps:
                if scope == MemoryScope.FULL:
                    # Full execution trace with all details
                    trace = self._format_execution_trace(turn.steps)
                    if trace:
                        messages.append(ModelRequest(parts=[SystemPromptPart(content=trace)]))
                elif scope == MemoryScope.LIGHTWEIGHT:
                    # Full query JSON for re-running
                    summary = self._format_query_summary(turn.steps, include_full_query=True)
                    if summary:
                        messages.append(ModelRequest(parts=[SystemPromptPart(content=summary)]))
                elif scope == MemoryScope.MINIMAL:
                    # Just query_id + one-liner
                    summary = self._format_query_summary(turn.steps, include_full_query=False)
                    if summary:
                        messages.append(ModelRequest(parts=[SystemPromptPart(content=summary)]))

            # Assistant response
            if turn.assistant_answer is not None:
                messages.append(ModelResponse(parts=[TextPart(content=turn.assistant_answer)]))

        # Always add current turn's user question
        if self.current_turn:
            messages.append(ModelRequest(parts=[UserPromptPart(content=self.current_turn.user_question)]))

        return messages

    def format_current_steps(self) -> str:
        """Format the steps taken in the current turn for display in prompts.

        Used to show what has been executed so far in this incomplete turn.
        """
        if not self.current_turn:
            return "None"

        all_steps = list(self.current_turn.steps)
        if self.current_turn.current_step:
            all_steps.append(self.current_turn.current_step)

        trace = self._format_execution_trace(all_steps)
        return trace if trace else "None"

    def format_context_for_llm(
        self,
        state,
        *,
        include_current_run_steps: bool = False,
    ) -> str:
        """Context formatter for LLM prompts.

        Current user request and conversation history are passed via
        message_history parameter, not included here.

        Args:
            state: SearchState instance for accessing current context
            include_current_run_steps: Show steps executed so far in current run

        Returns:
            Formatted context string ready to insert into prompt
        """
        if include_current_run_steps:
            steps = self.format_current_steps()
            return f"# Steps Already Executed\n{steps}"

        return ""
