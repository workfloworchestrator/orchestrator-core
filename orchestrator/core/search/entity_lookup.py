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

"""Direct-DB resolution of an entity id or id-prefix to (id, title).

This module is intentionally free of LLM/HTTP concerns so the resolver and the
id-form classifier are unit-testable in isolation. ``resolve_entity_id_prefix``
runs a cheap, deterministic prefix query against orchestrator-core tables — it
is not the semantic search engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import Text, cast, func

from orchestrator.core.db.database import WrappedSession
from orchestrator.core.db.models import (
    ProcessTable,
    ProductTable,
    SubscriptionTable,
    WorkflowTable,
)
from orchestrator.core.search.core.types import EntityType

MIN_PREFIX_LEN = 4
_HEX_CHARS = set("0123456789abcdef-")


@dataclass(frozen=True)
class ResolvedEntity:
    """A single id-prefix match: the full id and a human-readable title."""

    entity_id: str
    title: str


@dataclass(frozen=True)
class _LookupSpec:
    """Per-EntityType id column and title expression for a prefix query."""

    id_col: Any  # SQLAlchemy InstrumentedAttribute (the id/primary-key column)
    title_expr: Any  # SQLAlchemy column or computed expression yielding the title


_ENTITY_LOOKUP: dict[EntityType, _LookupSpec] = {
    EntityType.SUBSCRIPTION: _LookupSpec(SubscriptionTable.subscription_id, SubscriptionTable.description),
    EntityType.PRODUCT: _LookupSpec(ProductTable.product_id, ProductTable.name),
    EntityType.WORKFLOW: _LookupSpec(WorkflowTable.workflow_id, WorkflowTable.name),
    EntityType.PROCESS: _LookupSpec(
        ProcessTable.process_id,
        func.concat(cast(ProcessTable.workflow_id, Text), " (", ProcessTable.last_status, ")"),
    ),
}


class IdForm(Enum):
    """Classification of a raw id-or-prefix input."""

    FULL_UUID = "full_uuid"
    PREFIX = "prefix"
    TOO_SHORT = "too_short"
    NON_HEX = "non_hex"


def _classify_id(raw: str) -> tuple[IdForm, str]:
    """Normalize (strip + lower-case) an id-or-prefix and classify its form.

    Returns the classification and the normalized string. When the form is
    ``PREFIX`` the normalized string is the value to feed to a LIKE query.
    Length is measured in hex digits (hyphens ignored) against ``MIN_PREFIX_LEN``.
    """
    norm = raw.strip().lower()
    if not norm or any(char not in _HEX_CHARS for char in norm):
        return IdForm.NON_HEX, norm
    try:
        UUID(norm)
    except ValueError:
        if len(norm.replace("-", "")) < MIN_PREFIX_LEN:
            return IdForm.TOO_SHORT, norm
        return IdForm.PREFIX, norm
    return IdForm.FULL_UUID, norm


def resolve_entity_id_prefix(
    session: WrappedSession,
    entity_type: EntityType,
    prefix: str,
    limit: int,
) -> list[ResolvedEntity]:
    """Return entities whose id starts with ``prefix`` (case-insensitive), up to ``limit``.

    Fetches ``limit + 1`` rows so the caller can detect "more than limit" matches
    without a second count query. The prefix is matched against the id cast to
    text; on large tables this is a sequential scan, bounded by the limit.
    """
    spec = _ENTITY_LOOKUP[entity_type]
    rows = (
        session.query(spec.id_col, spec.title_expr)
        .filter(cast(spec.id_col, Text).ilike(f"{prefix}%"))
        .limit(limit + 1)
        .all()
    )
    return [ResolvedEntity(entity_id=str(row[0]), title=str(row[1])) for row in rows]
