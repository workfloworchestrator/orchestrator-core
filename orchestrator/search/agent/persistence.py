from typing import Any
from uuid import UUID

from pydantic_graph.persistence import BaseStatePersistence, EndSnapshot, NodeSnapshot
from sqlalchemy import select
from sqlalchemy.orm import Session
from structlog import get_logger

from orchestrator.db.models import GraphSnapshotTable
from orchestrator.search.agent.state import SearchState

logger = get_logger(__name__)


class PostgresStatePersistence(BaseStatePersistence[SearchState]):
    """PostgreSQL state persistence for search agent graphs.

    Stores NodeSnapshot and EndSnapshot objects in the graph_snapshots table,
    allowing graph execution to be interrupted and resumed across conversation turns.
    Uses thread_id for persistence so state continues across multiple runs in the same thread.
    """

    def __init__(self, thread_id: str, run_id: UUID, session: Session):
        """Initialize persistence with database session and thread ID.

        Args:
            thread_id: The conversation thread ID (persists across runs)
            run_id: The current run ID (stored with each snapshot for tracking)
            session: SQLAlchemy session for database operations
        """
        self.thread_id = thread_id
        self.run_id = run_id
        self.session = session
        self._sequence_counter = 0

    def record_run(self, snapshot_id: str):
        """Record that a run has started (returns an async context manager)."""
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _record():
            yield

        return _record()

    async def snapshot_node(self, state: SearchState, next_node: Any) -> None:
        """Save a node snapshot to PostgreSQL after node execution.

        Args:
            state: Current graph state
            next_node: The node that was executed
        """
        # Create a simple snapshot representation
        snapshot_data = {
            "kind": "node",
            "state": state.model_dump(mode="json"),
            "node": next_node.__class__.__name__,
            "sequence": self._sequence_counter,
        }

        db_snapshot = GraphSnapshotTable(
            run_id=self.run_id,
            sequence_number=self._sequence_counter,
            snapshot_data=snapshot_data,
        )

        self.session.add(db_snapshot)
        self.session.flush()

        logger.debug(
            "Saved node snapshot",
            run_id=str(self.run_id),
            sequence=self._sequence_counter,
            node=next_node.__class__.__name__,
        )

        self._sequence_counter += 1

    async def snapshot_node_if_new(self, snapshot_id: str, state: SearchState, next_node: Any) -> None:
        """Save a node snapshot only if it doesn't already exist.

        Args:
            snapshot_id: Unique identifier for this snapshot
            state: Current graph state
            next_node: The node that was just executed
        """
        stmt = select(GraphSnapshotTable).where(
            GraphSnapshotTable.run_id == self.run_id, GraphSnapshotTable.sequence_number == self._sequence_counter
        )
        result = self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            await self.snapshot_node(state, next_node)

    async def snapshot_end(self, state: SearchState, end: Any) -> None:
        """Save an end snapshot when the graph completes.

        Args:
            state: Final graph state
            end: The End node result
        """
        snapshot_data = {
            "kind": "end",
            "state": state.model_dump(mode="json"),
            "result": str(end.data) if hasattr(end, "data") else None,
            "sequence": self._sequence_counter,
        }

        db_snapshot = GraphSnapshotTable(
            run_id=self.run_id,
            sequence_number=self._sequence_counter,
            snapshot_data=snapshot_data,
        )

        self.session.add(db_snapshot)
        self.session.flush()

        logger.debug(
            "Saved end snapshot",
            run_id=str(self.run_id),
            sequence=self._sequence_counter,
        )

        self._sequence_counter += 1

    async def load_next(self) -> NodeSnapshot[SearchState] | None:
        """Retrieve a node snapshot with status 'created' and set its status to 'pending'.

        Loads across all runs in the thread to maintain context (e.g., query_id, results).
        Steps are tracked in environment.current_turn and reset at the start of each turn.

        Returns:
            The NodeSnapshot from the most recent snapshot, or None if no snapshots exist
        """
        from orchestrator.db.models import AgentRunTable

        # Get the latest snapshot from any run in this thread
        stmt = (
            select(GraphSnapshotTable)
            .join(AgentRunTable, GraphSnapshotTable.run_id == AgentRunTable.run_id)
            .where(AgentRunTable.thread_id == self.thread_id)
            .order_by(AgentRunTable.created_at.desc(), GraphSnapshotTable.sequence_number.desc())
            .limit(1)
        )

        result = self.session.execute(stmt)
        db_snapshot = result.scalar_one_or_none()

        if not db_snapshot:
            logger.debug("No snapshots found for thread", thread_id=self.thread_id)
            return None

        snapshot_data = db_snapshot.snapshot_data

        # Deserialize state from snapshot (works for both node and end snapshots)
        state_data = snapshot_data.get("state", {})
        state = SearchState.model_validate(state_data)

        # Update sequence counter to continue from where we left off
        self._sequence_counter = db_snapshot.sequence_number + 1

        logger.debug(
            "Loaded state for resume",
            thread_id=self.thread_id,
            run_id=str(self.run_id),
            sequence=db_snapshot.sequence_number,
        )

        # Note: we don't have the actual node object, so we pass None and provide an id
        # This is a custom usage pattern where we manually load state, not using Graph.iter_from_persistence()
        snapshot_id = f"snapshot_{self.run_id}_{db_snapshot.sequence_number}"
        return NodeSnapshot(state=state, node=None, id=snapshot_id)  # type: ignore

    async def load_all(self) -> list[NodeSnapshot[SearchState] | EndSnapshot[SearchState]]:
        """Load all snapshots for this run (for debugging/history).

        Returns:
            List of all snapshots in sequence order
        """
        from pydantic_graph import End

        stmt = (
            select(GraphSnapshotTable)
            .where(GraphSnapshotTable.run_id == self.run_id)
            .order_by(GraphSnapshotTable.sequence_number)
        )

        result = self.session.execute(stmt)
        db_snapshots = result.scalars().all()

        snapshots: list[NodeSnapshot[SearchState] | EndSnapshot[SearchState]] = []
        for db_snapshot in db_snapshots:
            snapshot_data = db_snapshot.snapshot_data
            snapshot_kind = snapshot_data.get("kind")

            # Deserialize state
            state_data = snapshot_data.get("state", {})
            state = SearchState.model_validate(state_data)

            if snapshot_kind == "end":
                # Create EndSnapshot with the result
                result_data = snapshot_data.get("result")
                end = End(result_data)
                snapshot_id = f"snapshot_{self.run_id}_{db_snapshot.sequence_number}"
                snapshot = EndSnapshot(state=state, result=end, id=snapshot_id)
            else:
                # Create NodeSnapshot without node object
                snapshot_id = f"snapshot_{self.run_id}_{db_snapshot.sequence_number}"
                snapshot = NodeSnapshot(state=state, node=None, id=snapshot_id)  # type: ignore

            snapshots.append(snapshot)

        logger.debug("Loaded all snapshots", run_id=str(self.run_id), count=len(snapshots))
        return snapshots
