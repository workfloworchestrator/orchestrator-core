# Copyright 2019-2026 SURF.
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

from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, ClassVar, cast
from uuid import uuid4

import structlog
from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import Query, Session, as_declarative, scoped_session, sessionmaker
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
    """Session subclass that can have its ``commit()`` temporarily disabled.

    Step bodies running under :func:`disable_commit` must not issue their own
    commits — the framework ``_run_step`` helper owns the transaction boundary
    around a step, so a nested commit inside the step body would break the
    outer :meth:`sqlalchemy.orm.Session.begin` context manager. This override
    silences such step-body commits while ``session.info["disabled"]`` is set
    (logging a warning so the step author notices during development) and
    forwards to the normal commit path otherwise.
    """

    def commit(self) -> None:
        if self.info.get("disabled", False):
            self.info.get("logger", logger).warning(
                "Step function tried to issue a commit. It should not! "
                "Will execute commit on behalf of step function when it returns."
            )
        else:
            super().commit()


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
        self.session_factory = sessionmaker(
            bind=self.engine, class_=WrappedSession, autocommit=False, autoflush=True, query_cls=SearchQuery
        )

        self.scoped_session = scoped_session(self.session_factory, self._scopefunc)
        BaseModel.set_query(cast(SearchQuery, cast(object, self.scoped_session.query_property())))

    def _scopefunc(self) -> str | None:
        return self.request_context.get()

    @property
    def session(self) -> WrappedSession:
        return self.scoped_session()

    @contextmanager
    def database_scope(self, **kwargs: Any) -> Generator["Database", None, None]:
        """Create a fresh SQLAlchemy Session bound to a new scope key.

        Each call sets a unique value in the ``request_context`` ContextVar so
        the underlying ``scoped_session`` yields a new Session instance. On
        exit the Session is removed from the registry and the ContextVar is
        reset to its prior value. Used by:

        * the HTTP request middleware (one scope per request),
        * the workflow executor (one outer scope per workflow run),
        * the per-step session manager in :func:`orchestrator.workflow._run_step`
          (two nested scopes per step — one for the work unit, one for the
          logging unit).

        Nested calls yield distinct Session instances and ``remove()`` on exit
        cleans only the innermost scope.

        Args:
            kwargs: Optional session kw args for this session
        """
        token = self.request_context.set(str(uuid4()))
        try:
            self.scoped_session(**kwargs)
            yield self
        finally:
            self.scoped_session.remove()
            self.request_context.reset(token)


@contextmanager
def disable_commit(db: "Database", log: BoundLogger) -> Iterator[None]:
    """Temporarily disable ``commit()`` on ``db.session`` for the duration of the block.

    While active, calls to :meth:`WrappedSession.commit` are silent no-ops
    (with a warning logged) so that code running inside the block — typically
    a workflow step body — cannot prematurely commit work that the framework
    intends to own via an outer :meth:`Session.begin` context manager.

    The guard is reentrant: if commit is already disabled when the block
    starts, the inner block leaves the flag alone and the outer block is
    responsible for clearing it.

    Args:
        db: The :class:`Database` whose current session should be guarded.
        log: A bound logger to attach to the session for warning messages.
    """
    restore = True
    if db.session.info.get("disabled", False):
        # Already disabled by an outer guard; this inner block is a no-op.
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


class DBSessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, database: Database, commit_on_exit: bool = False):
        super().__init__(app)
        self.commit_on_exit = commit_on_exit
        self.database = database

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        with self.database.database_scope():
            return await call_next(request)
