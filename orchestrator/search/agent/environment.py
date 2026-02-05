from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict

logger = structlog.get_logger(__name__)


@dataclass
class ActionRecord:
    action_type: str
    node_type: str
    description: str
    entity_type: str | None = None
    results_count: int = 0
    query_operation: str | None = None
    query_snapshot: dict | None = None
    success: bool = True
    error_message: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class CompletedTurn:
    user_question: str
    assistant_answer: str
    actions: list[ActionRecord]
    timestamp: datetime


@dataclass
class CurrentTurn:
    user_question: str
    actions: list[ActionRecord] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class CurrentContext:
    last_action: ActionRecord | None = None
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
        self.current_turn = CurrentTurn(user_question=user_question, actions=[])
        # Preserve context from previous turn (query_id, results_available, etc.)
        # Only reset last_action since we're starting fresh actions for this turn
        self.current_context = CurrentContext(
            last_action=None,
            query_id=self.current_context.query_id,
            results_available=self.current_context.results_available,
            export_url=self.current_context.export_url,
        )

    def record_action(self, action: ActionRecord):
        if not self.current_turn:
            raise ValueError("No active turn")
        self.current_turn = CurrentTurn(
            user_question=self.current_turn.user_question,
            actions=list(self.current_turn.actions) + [action],
            timestamp=self.current_turn.timestamp,
        )
        self.current_context = CurrentContext(
            last_action=action,
            query_id=self.current_context.query_id,
            results_available=(
                action.results_count > 0
                if action.action_type in ("search", "aggregation")
                else self.current_context.results_available
            ),
            export_url=self.current_context.export_url,
        )

    def complete_turn(self, assistant_answer: str, query_id: UUID | None = None):
        if not self.current_turn:
            raise ValueError("No active turn")

        logger.debug(
            "complete_turn: before",
            completed_count_before=len(self.completed_turns),
            current_turn_question=self.current_turn.user_question,
            action_count=len(self.current_turn.actions),
        )

        completed = CompletedTurn(
            user_question=self.current_turn.user_question,
            assistant_answer=assistant_answer,
            actions=list(self.current_turn.actions),
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
                last_action=self.current_context.last_action,
                query_id=query_id,
                results_available=self.current_context.results_available,
                export_url=self.current_context.export_url,
            )
        self.current_turn = None

    def format_for_llm(self, max_turns: int = 5) -> str:
        recent = self.completed_turns[-max_turns:]
        if not recent:
            return "[No previous conversation]"
        sections = []
        for turn in recent:
            sections.append(f"user: {turn.user_question}")
            if turn.actions:
                actions_text = ", ".join([action.description for action in turn.actions])
                sections.append(f"[actions: {actions_text}]")
            sections.append(f"assistant: {turn.assistant_answer}")
        return "\n".join(sections)

    def format_current_turn(self) -> str:
        if not self.current_turn:
            return "[First action for this request]"
        lines = [f"user: {self.current_turn.user_question}"]
        if self.current_turn.actions:
            actions_text = ", ".join([action.description for action in self.current_turn.actions])
            lines.append(f"[actions: {actions_text}]")
        else:
            lines.append("[no actions yet]")
        return "\n".join(lines)

    def format_current_context(self) -> str:
        # Show context if we have any ongoing state from previous turns
        if not self.current_context.query_id and not self.current_context.results_available:
            return "[No context available]"

        lines = []
        if self.current_context.last_action:
            action = self.current_context.last_action
            lines.extend(
                [
                    f"Last action: {action.description}",
                    f"Type: {action.action_type}",
                    f"Results: {action.results_count}" if action.results_count else "No results",
                    f"Status: {'Success' if action.success else 'Failed'}",
                ]
            )

        if self.current_context.results_available:
            lines.append("Results available for follow-up actions (export/details)")
        if self.current_context.export_url:
            lines.append(f"Export ready at: {self.current_context.export_url}")

        return "\n".join(lines) if lines else "[No context available]"
