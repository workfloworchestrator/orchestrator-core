"""Add agent_runs and agent_queries tables.

Revision ID: 459f352f5aa6
Revises: 850dccac3b02
Create Date: 2025-10-09 00:52:16.297143

"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql
from sqlalchemy_utils import UUIDType

# revision identifiers, used by Alembic.
revision = "459f352f5aa6"
down_revision = "850dccac3b02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("run_id", UUIDType(), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("agent_type", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("current_timestamp"), nullable=False
        ),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_agent_runs_created_at", "agent_runs", ["created_at"])

    op.create_table(
        "agent_queries",
        sa.Column("query_id", UUIDType(), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("run_id", UUIDType(), nullable=False),
        sa.Column("query_number", sa.Integer(), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("query_embedding", Vector(1536), nullable=True),
        sa.Column(
            "executed_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("current_timestamp"), nullable=False
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("query_id"),
        sa.UniqueConstraint("run_id", "query_number", name="uq_run_query_number"),
    )
    op.create_index("ix_agent_queries_run_id", "agent_queries", ["run_id"])
    op.create_index("ix_agent_queries_executed_at", "agent_queries", ["executed_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_queries_executed_at", table_name="agent_queries")
    op.drop_index("ix_agent_queries_run_id", table_name="agent_queries")
    op.drop_table("agent_queries")

    op.drop_index("ix_agent_runs_created_at", table_name="agent_runs")
    op.drop_table("agent_runs")
