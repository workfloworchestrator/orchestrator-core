# Copyright 2019-2020 SURF.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import time
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, ClassVar, cast
from uuid import uuid4

import structlog
from psycopg.pq import TransactionStatus
from sqlalchemy import create_engine, event
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import Query, Session, as_declarative, scoped_session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry
from sqlalchemy.sql.schema import MetaData
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
from structlog.stdlib import BoundLogger

from orchestrator.utils.json import json_dumps, json_loads

logger = structlog.get_logger(__name__)


class SearchQuery(Query):
    """Custom Query class to have search() property."""

    pass


class NoSessionError(RuntimeError):
    pass


class BaseModelMeta(DeclarativeMeta):
    """Using this metaclass means that we can set and access query as a property at a class level."""

    def set_query(self, query: SearchQuery) -> None:
        self._query = query

    @property
    def query(self) -> SearchQuery:
        if self._query is not None:
            return self._query
        raise NoSessionError("Cant get session. Please, call BaseModel.set_query() first")


@as_declarative(metaclass=BaseModelMeta)
class _Base:
    """SQLAlchemy base class."""

    __abstract__ = True

    _json_include: list = []
    _json_exclude: list = []

    def __json__(self, excluded_keys: set = set()) -> dict:  # noqa: B006
        ins: Any = sa_inspect(self)

        columns = set(ins.mapper.column_attrs.keys())
        relationships = set(ins.mapper.relationships.keys())
        unloaded = ins.unloaded
        expired = ins.expired_attributes
        include = set(self._json_include)
        exclude = set(self._json_exclude) | set(excluded_keys)

        # This set of keys determines which fields will be present in
        # the resulting JSON object.
        # Here we initialize it with properties defined by the model class,
        # and then add/delete some columns below in a tricky way.
        keys = columns | relationships

        # 1. Remove not yet loaded properties.
        # Basically this is needed to serialize only .join()'ed relationships
        # and omit all other lazy-loaded things.
        if not ins.transient:
            # If the entity is not transient -- exclude unloaded keys
            # Transient entities won't load these anyway, so it's safe to
            # include all columns and get defaults
            keys -= unloaded

        # 2. Re-load expired attributes.
        # At the previous step (1) we substracted unloaded keys, and usually
        # that includes all expired keys. Actually we don't want to remove the
        # expired keys, we want to refresh them, so here we have to re-add them
        # back. And they will be refreshed later, upon first read.
        if ins.expired:
            keys |= expired

        # 3. Add keys explicitly specified in _json_include list.
        # That allows you to override those attributes unloaded above.
        # For example, you may include some lazy-loaded relationship() there
        # (which is usually removed at the step 1).
        keys |= include

        # 4. For objects in `deleted` or `detached` state, remove all
        # relationships and lazy-loaded attributes, because they require
        # refreshing data from the DB, but this cannot be done in these states.
        # That is:
        #  - if the object is deleted, you can't refresh data from the DB
        #    because there is no data in the DB, everything is deleted
        #  - if the object is detached, then there is no DB session associated
        #    with the object, so you don't have a DB connection to send a query
        # So in both cases you get an error if you try to read such attributes.
        if ins.deleted or ins.detached:
            keys -= relationships
            keys -= unloaded

        # 5. Delete all explicitly black-listed keys.
        # That should be done last, since that may be used to hide some
        # sensitive data from JSON representation.
        keys -= exclude

        return {key: getattr(self, key) for key in keys}


class BaseModel(_Base):
    """Separate BaseModel class to be able to include mixins and to Fix typing.

    This should be used instead of Base.
    """

    metadata: ClassVar[MetaData]
    query: ClassVar[SearchQuery]
    set_query: ClassVar[Callable[[SearchQuery], None]]

    __abstract__ = True

    __init__: Callable[..., None]

    def __repr__(self) -> str:
        inst_state: Any = sa_inspect(self)
        attr_vals = [
            f"{attr.key}={getattr(self, attr.key)}"
            for attr in inst_state.mapper.column_attrs
            if attr.key not in ["tsv"]
        ]
        return f"{self.__class__.__name__}({', '.join(attr_vals)})"


class WrappedSession(Session):
    """This Session class allows us to disable commit during steps."""

    def commit(self) -> None:
        if self.info.get("disabled", False):
            self.info.get("logger", logger).warning(
                "Step function tried to issue a commit. It should not! "
                "Will execute commit on behalf of step function when it returns."
            )
        else:
            t = self._transaction
            logger.debug(
                "WrappedSession.commit",
                transaction_type=type(t).__name__,
                nested=getattr(t, "nested", None),
                is_active=getattr(t, "is_active", None),
                parent=type(getattr(t, "parent", None)).__name__,
                transaction_id=id(t),
                state=getattr(t, "state", None),
                connections=len(getattr(t, "connections", [])),
            )
            super().commit()
            logger.debug(
                "WrappedSession.commit",
                transaction_type=type(t).__name__,
                nested=getattr(t, "nested", None),
                is_active=getattr(t, "is_active", None),
                parent=type(getattr(t, "parent", None)).__name__,
                transaction_id=id(t),
                state=getattr(t, "state", None),
                connections=len(getattr(t, "connections", [])),
            )


ENGINE_ARGUMENTS = {
    "connect_args": {"connect_timeout": 10, "options": "-c timezone=UTC"},
    "pool_pre_ping": True,
    "pool_size": 60,
    "json_serializer": json_dumps,
    "json_deserializer": json_loads,
}
SESSION_ARGUMENTS = {"class_": WrappedSession, "autocommit": False, "autoflush": True, "query_cls": SearchQuery}


class Database:
    """Setup and contain our database connection.

    This is used to be able to set up the database in a uniform way while allowing easy testing and session management.

    Session management is done using ``scoped_session`` with a special scopefunc, because we cannot use
    threading.local(). Contextvar does the right thing with respect to asyncio and behaves similar to threading.local().
    We only store a random string in the contextvar and let scoped session do the heavy lifting. This allows us to
    easily start a new session or get the existing one using the scoped_session mechanics.
    """

    def __init__(self, db_url: str) -> None:
        self.request_context: ContextVar[str] = ContextVar("request_context", default="")
        self.engine = create_engine(db_url, **ENGINE_ARGUMENTS)
        self._register_pool_events()
        self.session_factory = sessionmaker(
            bind=self.engine, class_=WrappedSession, autocommit=False, autoflush=True, query_cls=SearchQuery
        )

        self.scoped_session = scoped_session(self.session_factory, self._scopefunc)
        BaseModel.set_query(cast(SearchQuery, self.scoped_session.query_property()))

    def _register_pool_events(self) -> None:
        """Register connection pool events to ensure proper transaction cleanup.

        With psycopg3, connections can retain transaction state ("idle in transaction")
        if not properly committed or rolled back. This ensures that connections returned
        to the pool are always in a clean state, preventing lock contention between
        concurrent workers.
        """

        @event.listens_for(self.engine, "checkin")
        def _on_checkin(dbapi_connection: Any, connection_record: ConnectionPoolEntry) -> None:
            try:
                # psycopg3 exposes transaction_status via connection.info
                tx_status = getattr(getattr(dbapi_connection, "info", None), "transaction_status", None)
                if tx_status is not None and tx_status != TransactionStatus.IDLE:
                    # Try to get the last query for context
                    last_query = None
                    try:
                        last_query = getattr(dbapi_connection, "status", None)
                    except Exception:
                        pass
                    logger.warning(
                        "Connection returned to pool with active transaction, forcing rollback",
                        transaction_status=tx_status.name if hasattr(tx_status, "name") else str(tx_status),
                        last_query_hint=last_query,
                    )
                    dbapi_connection.rollback()
                    logger.debug("Forced rollback completed on checkin")
            except Exception:
                logger.warning("Failed to clean up connection on pool checkin, invalidating")
                connection_record.invalidate()

        @event.listens_for(self.engine, "checkout")
        def _on_checkout(dbapi_connection: Any, connection_record: ConnectionPoolEntry, connection_proxy: Any) -> None:
            tx_status = getattr(getattr(dbapi_connection, "info", None), "transaction_status", None)
            if tx_status is not None and tx_status != TransactionStatus.IDLE:
                logger.warning(
                    "Connection checked out from pool with active transaction",
                    transaction_status=tx_status.name if hasattr(tx_status, "name") else str(tx_status),
                )

    def _scopefunc(self) -> str | None:
        return self.request_context.get()

    @property
    def session(self) -> WrappedSession:
        return self.scoped_session()

    @contextmanager
    def database_scope(self, **kwargs: Any) -> Generator["Database", None, None]:
        """Create a new database session (scope).

        This creates a new database session to handle all the database connection from a single scope (request or workflow).
        This method should typically only been called in request middleware or at the start of workflows.

        Args:
            kwargs: Optional session kw args for this session
        """
        token = self.request_context.set(str(uuid4()))
        self.scoped_session(**kwargs)
        scope_start = time.monotonic()
        logger.debug("Database scope opened")
        try:
            yield self
        finally:
            elapsed = time.monotonic() - scope_start
            if elapsed > 5.0:
                logger.warning(
                    "Database scope was open for extended period",
                    elapsed_seconds=round(elapsed, 3),
                )
            else:
                logger.debug("Database scope closing", elapsed_seconds=round(elapsed, 3))
            try:
                # Explicitly rollback any uncommitted transaction before closing the session.
                # With psycopg3, Session.close() does NOT rollback, which can leave connections
                # in "idle in transaction" state when returned to the pool, causing lock contention.
                self.scoped_session.rollback()
            except Exception:
                logger.debug("Rollback during database_scope cleanup failed, session will be removed")
            self.scoped_session.remove()
            self.request_context.reset(token)


class DBSessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, database: Database, commit_on_exit: bool = False):
        super().__init__(app)
        self.commit_on_exit = commit_on_exit
        self.database = database

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        with self.database.database_scope():
            return await call_next(request)


@contextmanager
def disable_commit(db: Database, log: BoundLogger) -> Iterator:
    restore = True
    # If `db.session` already has its `commit` method disabled we won't try disabling *and* restoring it again.
    if db.session.info.get("disabled", False):
        restore = False
    else:
        log.debug("Temporarily disabling commit.")
        db.session.info["disabled"] = True
        db.session.info["logger"] = log
    try:
        yield
    finally:
        if restore:
            log.debug("Reenabling commit.")
            db.session.info["disabled"] = False
            db.session.info["logger"] = None


@contextmanager
def transactional(db: Database, log: BoundLogger) -> Iterator:
    """Run a step function in an implicit transaction with automatic rollback or commit.

    It will roll back in case of error, commit otherwise. It will also disable the `commit()` method
    on `BaseModel.session` for the time `transactional` is in effect.
    """
    try:
        with disable_commit(db, log):
            yield
        log.debug("Committing transaction.")
        db.session.commit()
    except Exception:
        log.warning("Rolling back transaction.")
        raise
    finally:
        # Extra safeguard rollback. If the commit failed there is still a failed transaction open.
        # BTW: without a transaction in progress this method is a pass-through.
        db.session.rollback()
        db.session.close()
