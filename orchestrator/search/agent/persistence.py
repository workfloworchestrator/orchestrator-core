from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from structlog import get_logger

from orchestrator.db.models import GraphSnapshotTable
from orchestrator.search.agent.state import SearchState

logger = get_logger(__name__)


class PostgresStatePersistence:
    """PostgreSQL state persistence for search agent.

    Stores state snapshots in the graph_snapshots table, allowing execution to be
    interrupted and resumed across conversation turns.
    Uses thread_id for persistence so state continues across multiple runs in the same thread.
    """

    def __init__(self, thread_id: str, run_id: UUID, session: Session):
        self.thread_id = thread_id
        self.run_id = run_id
        self.session = session
        self._sequence_counter = 0

    async def snapshot(self, state: SearchState) -> None:
        """Save a state snapshot to PostgreSQL.

        Args:
            state: Current agent state
        """
        snapshot_data = {
            "state": state.model_dump(mode="json"),
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
            "Saved state snapshot",
            run_id=str(self.run_id),
            sequence=self._sequence_counter,
        )

        self._sequence_counter += 1

    async def load_state(self) -> SearchState | None:
        """Load the most recent state for this thread.

        Returns:
            The deserialized SearchState, or None if no snapshots exist
        """
        from orchestrator.db.models import AgentRunTable

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

        return state
