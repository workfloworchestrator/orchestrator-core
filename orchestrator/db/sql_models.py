import uuid
from datetime import datetime
from typing import Any, Generator, List, Optional

from sqlalchemy import Column, String, Text, text
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy_utils import UUIDType
from sqlmodel import Field, Relationship, Session, SQLModel

from orchestrator.config.assignee import Assignee
from orchestrator.db import db
from orchestrator.db.models import UtcTimestamp
from orchestrator.utils.datetime import nowtz
from orchestrator.version import GIT_COMMIT_HASH


def get_session() -> Generator[Session, None, None]:
    with Session(db.engine) as session:
        yield session


class ProcessSQLModel(SQLModel, table=True):  # type: ignore
    __tablename__ = "processes"

    pid: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True, index=True),
    )
    workflow: str = Field(sa_column=Column(String(255), nullable=False))
    assignee: str = Field(sa_column=Column(String(50), server_default=Assignee.SYSTEM, nullable=False))
    last_status: str = Field(sa_column=Column(String(50), nullable=False))
    last_step: str = Field(sa_column=Column(String(255), nullable=True))
    failed_reason: str | None = Field(sa_column=Column(Text()))
    traceback: str | None = Field(sa_column=Column(Text()))
    created_by: str | None = Field(sa_column=Column(String(255), nullable=True))
    is_task: bool = Field(default=False, index=True)
    started_at: datetime = Field(
        sa_column=Column(UtcTimestamp, server_default=text("current_timestamp()"), nullable=False)
    )
    last_modified_at: datetime = Field(
        sa_column=Column(UtcTimestamp, server_default=text("current_timestamp()"), onupdate=nowtz, nullable=False)
    )

    steps: List["StepSQLModel"] = Relationship(back_populates="process")


class StepSQLModel(SQLModel, table=True):  # type: ignore
    __tablename__ = "process_steps"

    stepid: Optional[uuid.UUID] = Field(
        default=None, sa_column=Column(UUIDType, server_default=text("uuid_generate_v4()"), primary_key=True)
    )
    name: str = Field(sa_column=Column(String(), nullable=False))
    status: str = Field(sa_column=Column(String(50), nullable=False))
    state: dict[str, Any] = Field(sa_column=Column(pg.JSONB(), nullable=False))
    created_by: datetime | None = Field(sa_column=Column(String(255), nullable=True))
    executed_at: datetime | None = Field(
        sa_column=Column(UtcTimestamp, server_default=text("statement_timestamp()"), nullable=False)
    )
    commit_hash: str | None = Field(sa_column=Column(String(40), nullable=True, default=GIT_COMMIT_HASH))

    pid: Optional[uuid.UUID] = Field(alias="process_id", default=None, foreign_key="processes.pid")
    process: ProcessSQLModel = Relationship(back_populates="steps")
