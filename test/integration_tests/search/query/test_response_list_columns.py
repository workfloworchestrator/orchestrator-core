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

"""Integration tests for list-valued response_columns against the real ai_search_index table."""

from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from pydantic import ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.core.domain.base import SubscriptionModel
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.indexing.field_types import clear_field_type_cache
from orchestrator.core.search.query.builder import (
    build_response_list_rows_query,
    process_response_list_columns,
    split_response_columns,
)
from orchestrator.core.search.query.engine import _fetch_response_column_data
from test.unit_tests.search.fixtures.blocks import BasicBlock, NestedBlock

pytestmark = pytest.mark.search


def _add_index_row(
    path: str,
    *,
    value_type: FieldType = FieldType.STRING,
    entity_type: str = "PROCESS",
    entity_id: UUID | None = None,
    value: str = "v",
) -> UUID:
    """Insert one ai_search_index row and return its entity_id."""
    eid = entity_id or uuid4()
    db.session.add(
        AiSearchIndex(
            entity_type=entity_type,
            entity_id=eid,
            path=Ltree(path),
            value=value,
            content_hash="0" * 64,
            value_type=value_type,
        )
    )
    db.session.flush()
    return eid


def test_list_rows_query_returns_grouped_subscriptions_in_order():
    process_id = uuid4()
    _add_index_row("process.subscriptions.0.subscription_id", entity_id=process_id, value="uuid1")
    _add_index_row("process.subscriptions.0.description", entity_id=process_id, value="desc1")
    _add_index_row("process.subscriptions.1.subscription_id", entity_id=process_id, value="uuid2")
    _add_index_row("process.subscriptions.1.description", entity_id=process_id, value="desc2")

    list_paths = ["process.subscriptions.*.subscription_id", "process.subscriptions.*.description"]
    stmt = build_response_list_rows_query([str(process_id)], EntityType.PROCESS, list_paths)
    rows = db.session.execute(stmt).all()

    result = process_response_list_columns(rows, list_paths)

    assert result == {
        "process.subscriptions": {
            str(process_id): [
                {"subscription_id": "uuid1", "description": "desc1"},
                {"subscription_id": "uuid2", "description": "desc2"},
            ]
        }
    }


def test_list_rows_query_excludes_other_entities_and_entity_types():
    process_id = uuid4()
    other_process_id = uuid4()
    _add_index_row("process.subscriptions.0.subscription_id", entity_id=process_id, value="uuid1")
    _add_index_row("process.subscriptions.0.subscription_id", entity_id=other_process_id, value="uuid-other")
    # Same path shape but a different entity_type -- must not leak in.
    _add_index_row(
        "process.subscriptions.0.subscription_id", entity_id=uuid4(), entity_type="SUBSCRIPTION", value="uuid-sub"
    )

    list_paths = ["process.subscriptions.*.subscription_id"]
    stmt = build_response_list_rows_query([str(process_id)], EntityType.PROCESS, list_paths)
    rows = db.session.execute(stmt).all()

    result = process_response_list_columns(rows, list_paths)

    assert result == {"process.subscriptions": {str(process_id): [{"subscription_id": "uuid1"}]}}


def test_list_rows_query_returns_empty_when_no_subscriptions_indexed():
    process_id = uuid4()
    _add_index_row("process.workflow_name", entity_id=process_id, value="create_service")

    list_paths = ["process.subscriptions.*.subscription_id"]
    stmt = build_response_list_rows_query([str(process_id)], EntityType.PROCESS, list_paths)
    rows = db.session.execute(stmt).all()

    result = process_response_list_columns(rows, list_paths)

    assert result == {"process.subscriptions": {}}


def test_list_rows_query_multiple_prefixes_in_one_round_trip():
    """Wildcard paths with two distinct prefixes are fetched together and split back out by prefix."""
    process_id = uuid4()
    _add_index_row("process.subscriptions.0.subscription_id", entity_id=process_id, value="uuid1")
    _add_index_row("process.products.0.name", entity_id=process_id, value="product1")

    list_paths = ["process.subscriptions.*.subscription_id", "process.products.*.name"]
    stmt = build_response_list_rows_query([str(process_id)], EntityType.PROCESS, list_paths)
    rows = db.session.execute(stmt).all()

    result = process_response_list_columns(rows, list_paths)

    assert result == {
        "process.subscriptions": {str(process_id): [{"subscription_id": "uuid1"}]},
        "process.products": {str(process_id): [{"name": "product1"}]},
    }


def test_wildcard_free_column_under_nested_lists_fetches_real_rows():
    """A caller-supplied path with no wildcard reaches rows that were indexed under the inner list.

    Covers the auto-detect path end to end: registering both products makes `subscription.container`
    and `subscription.container.list_blocks` list fields, and only wildcarding at the inner one
    produces an lquery matching the rows below.
    """

    class ShallowListSubscription(SubscriptionModel, is_base=True):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        container: list[BasicBlock]

    class DeepListSubscription(SubscriptionModel, is_base=True):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        container: NestedBlock

    subscription_id = uuid4()
    _add_index_row(
        "subscription.container.list_blocks.0.name",
        entity_type="SUBSCRIPTION",
        entity_id=subscription_id,
        value="first",
    )
    _add_index_row(
        "subscription.container.list_blocks.1.name",
        entity_type="SUBSCRIPTION",
        entity_id=subscription_id,
        value="second",
    )

    registry = {"SHALLOW": ShallowListSubscription, "DEEP": DeepListSubscription}
    clear_field_type_cache()
    try:
        with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, registry, clear=True):
            flat, list_paths = split_response_columns(
                ["subscription.container.list_blocks.name"], EntityType.SUBSCRIPTION
            )
            stmt = build_response_list_rows_query([str(subscription_id)], EntityType.SUBSCRIPTION, list_paths)
            rows = db.session.execute(stmt).all()
    finally:
        clear_field_type_cache()

    assert flat == []
    assert list_paths == ["subscription.container.list_blocks.*.name"]
    assert process_response_list_columns(rows, list_paths) == {
        "subscription.container.list_blocks": {str(subscription_id): [{"name": "first"}, {"name": "second"}]}
    }


# --- CodSpeed benchmarks for _fetch_response_column_data's flat, list, and combined paths ---

_BENCHMARK_ENTITY_COUNT = 100
_BENCHMARK_SUBSCRIPTIONS_PER_PROCESS = 5

_BENCHMARK_FLAT_COLUMNS = ["process.workflow_name", "process.last_step"]
_BENCHMARK_LIST_COLUMNS = ["process.subscriptions.subscription_id", "process.subscriptions.description"]


def _benchmark_flat_rows(process_id: UUID) -> list[AiSearchIndex]:
    return [
        AiSearchIndex(
            entity_type=EntityType.PROCESS,
            entity_id=process_id,
            path=Ltree(path),
            value=f"{path}-value",
            value_type=FieldType.STRING,
            content_hash=uuid4().hex,
        )
        for path in _BENCHMARK_FLAT_COLUMNS
    ]


def _benchmark_list_rows(process_id: UUID) -> list[AiSearchIndex]:
    return [
        AiSearchIndex(
            entity_type=EntityType.PROCESS,
            entity_id=process_id,
            path=Ltree(f"process.subscriptions.{index}.{suffix}"),
            value=f"{suffix}-{index}",
            value_type=FieldType.STRING,
            content_hash=uuid4().hex,
        )
        for index in range(_BENCHMARK_SUBSCRIPTIONS_PER_PROCESS)
        for suffix in ("subscription_id", "description")
    ]


@pytest.fixture
def indexed_processes_for_benchmark() -> list[str]:
    """`_BENCHMARK_ENTITY_COUNT` processes, each with flat fields and a list of subscriptions indexed.

    Fixtures execute once per benchmark and are excluded from the measurement, so the row count
    only needs to be large enough for the query cost to be representative, not huge.
    """
    process_ids = [uuid4() for _ in range(_BENCHMARK_ENTITY_COUNT)]
    db.session.add_all(
        [
            row
            for process_id in process_ids
            for row in (*_benchmark_flat_rows(process_id), *_benchmark_list_rows(process_id))
        ]
    )
    db.session.commit()
    return [str(process_id) for process_id in process_ids]


@pytest.mark.benchmark
async def test_fetch_response_column_data_flat_paths_benchmark(
    indexed_processes_for_benchmark: list[str], async_session: AsyncSession
) -> None:
    """Only flat (scalar) response columns requested -- exercises the pivot-query path alone."""
    result = await _fetch_response_column_data(
        indexed_processes_for_benchmark, EntityType.PROCESS, _BENCHMARK_FLAT_COLUMNS, async_session
    )

    assert result is not None
    assert all(set(columns) == set(_BENCHMARK_FLAT_COLUMNS) for columns in result.values())


@pytest.mark.benchmark
async def test_fetch_response_column_data_list_paths_benchmark(
    indexed_processes_for_benchmark: list[str], async_session: AsyncSession
) -> None:
    """Only wildcard list response columns requested -- exercises the list-rows query path alone."""
    result = await _fetch_response_column_data(
        indexed_processes_for_benchmark, EntityType.PROCESS, _BENCHMARK_LIST_COLUMNS, async_session
    )

    assert result is not None
    assert all(
        columns["process.subscriptions"]
        == [
            {"description": f"description-{i}", "subscription_id": f"subscription_id-{i}"}
            for i in range(_BENCHMARK_SUBSCRIPTIONS_PER_PROCESS)
        ]
        for columns in result.values()
    )


@pytest.mark.benchmark
async def test_fetch_response_column_data_flat_and_list_paths_benchmark(
    indexed_processes_for_benchmark: list[str], async_session: AsyncSession
) -> None:
    """Both flat and list response columns requested together -- exercises both query paths in one call."""
    result = await _fetch_response_column_data(
        indexed_processes_for_benchmark,
        EntityType.PROCESS,
        [*_BENCHMARK_FLAT_COLUMNS, *_BENCHMARK_LIST_COLUMNS],
        async_session,
    )

    assert result is not None
    assert all(set(columns) == {*_BENCHMARK_FLAT_COLUMNS, "process.subscriptions"} for columns in result.values())
