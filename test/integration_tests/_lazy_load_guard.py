# Copyright 2019-2026 SURF, GÉANT.
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

"""Fail tests on ORM loads an ``AsyncSession`` could not have performed.

An ``AsyncSession`` runs every awaited operation inside a greenlet that SQLAlchemy spawns
for it. Attribute access that falls outside such a greenlet — a lazy relationship load or a
deferred column read during response serialization, for instance — has no way to suspend for
IO and raises ``MissingGreenlet`` against a real async driver.

Integration tests bind their ``AsyncSession`` to the synchronous test connection, which makes
those loads succeed as ordinary blocking queries and hides the failure. Registering
:func:`install` on such a session restores the distinction: it reproduces the driver's own
precondition without needing the driver.
"""

import greenlet
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import ORMExecuteState

# Relationship and column loads that are known to be emitted outside greenlet context and have
# not been given eager loading yet. Entries are "<Mapper>.<attribute>" as reported below.
#
# This allowlist must only ever SHRINK. Fix the query that owns the load — add the relationship
# to its loader options — and delete the entry.
KNOWN_IMPLICIT_LOADS: frozenset[str] = frozenset()


class ImplicitAsyncLoadError(AssertionError):
    """An ORM load was emitted where a real async driver would have raised ``MissingGreenlet``."""


def _can_suspend_for_io() -> bool:
    """Whether the current greenlet is one SQLAlchemy spawned to await IO on."""
    return bool(getattr(greenlet.getcurrent(), "__sqlalchemy_greenlet_provider__", False))


def _describe(execute_state: ORMExecuteState) -> str:
    """Name the attribute being loaded as "<Mapper>.<attribute>", falling back to the mapper."""
    path = execute_state.loader_strategy_path
    if path is not None:
        entity = getattr(path.parent, "entity", None)
        mapper = getattr(entity, "class_", None) or getattr(entity, "entity", None)
        prop = getattr(path, "prop", None)
        if mapper is not None and prop is not None:
            return f"{mapper.__name__}.{prop.key}"

    if (loaded_from := execute_state.lazy_loaded_from) is not None:
        return f"{loaded_from.class_.__name__}.<unknown>"

    bind_mapper = execute_state.bind_mapper
    return f"{bind_mapper.class_.__name__}.<unknown>" if bind_mapper is not None else "<unknown>"


def _handler(execute_state: ORMExecuteState) -> None:
    if _can_suspend_for_io():
        return
    if not (execute_state.is_relationship_load or execute_state.is_column_load):
        return

    description = _describe(execute_state)
    if description in KNOWN_IMPLICIT_LOADS:
        return

    raise ImplicitAsyncLoadError(
        f"{description} was loaded outside greenlet context. Against the async driver this "
        f"raises MissingGreenlet, so the query that produced this object must eager-load it. "
        f"Statement: {execute_state.statement}"
    )


def install(session: AsyncSession) -> None:
    """Fail this session on any relationship or column load emitted outside greenlet context."""
    event.listen(session.sync_session, "do_orm_execute", _handler)


def uninstall(session: AsyncSession) -> None:
    """Remove the guard registered by :func:`install`."""
    event.remove(session.sync_session, "do_orm_execute", _handler)
