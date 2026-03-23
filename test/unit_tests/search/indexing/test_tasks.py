# Copyright 2019-2025 SURF, GÉANT.
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

from contextlib import contextmanager
from unittest.mock import MagicMock, call, patch

import pytest
from sqlalchemy.orm import Query

from orchestrator.search.core.types import EntityType
from orchestrator.search.indexing.tasks import _get_entity_count, run_indexing_for_entity

pytestmark = pytest.mark.search

VALID_UUID = "12345678-1234-1234-1234-123456789abc"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_db(scalar_return: int | None = 42) -> MagicMock:
    """Build a mock db whose session.execute().scalar() returns scalar_return."""
    mock_db = MagicMock()
    mock_db.session.execute.return_value.scalar.return_value = scalar_return
    return mock_db


def _make_mock_stmt() -> MagicMock:
    """Build a mock Select statement that supports .subquery(), .execution_options()."""
    stmt = MagicMock()
    stmt.subquery.return_value = MagicMock()
    stmt.execution_options.return_value = stmt
    return stmt


def _make_mock_registry_config(query_return: MagicMock) -> MagicMock:
    """Return a mock ENTITY_CONFIG_REGISTRY dict with a single SUBSCRIPTION entry."""
    config = MagicMock()
    config.get_all_query.return_value = query_return
    return {EntityType.SUBSCRIPTION: config}


# ---------------------------------------------------------------------------
# _get_entity_count
# ---------------------------------------------------------------------------


class TestGetEntityCount:
    def test_returns_count_from_session(self) -> None:
        mock_db = _make_mock_db(scalar_return=42)
        mock_subquery = MagicMock()

        with (
            patch("orchestrator.search.indexing.tasks.db", mock_db),
            patch("orchestrator.search.indexing.tasks.select") as mock_select,
            patch("orchestrator.search.indexing.tasks.func"),
        ):
            mock_stmt = MagicMock()
            mock_stmt.subquery.return_value = mock_subquery
            mock_select.return_value.select_from.return_value = MagicMock()
            result = _get_entity_count(mock_stmt)

        assert result == 42

    def test_returns_none_when_scalar_is_none(self) -> None:
        mock_db = _make_mock_db(scalar_return=None)
        mock_subquery = MagicMock()

        with (
            patch("orchestrator.search.indexing.tasks.db", mock_db),
            patch("orchestrator.search.indexing.tasks.select") as mock_select,
            patch("orchestrator.search.indexing.tasks.func"),
        ):
            mock_stmt = MagicMock()
            mock_stmt.subquery.return_value = mock_subquery
            mock_select.return_value.select_from.return_value = MagicMock()
            result = _get_entity_count(mock_stmt)

        assert result is None


# ---------------------------------------------------------------------------
# run_indexing_for_entity
# ---------------------------------------------------------------------------


@contextmanager
def _noop_context():
    yield


class TestRunIndexingForEntity:
    def _patches(
        self,
        registry: dict,
        mock_db: MagicMock,
        mock_indexer_cls: MagicMock,
        cache_ctx: MagicMock | None = None,
    ):
        """Return a list of patch context managers for run_indexing_for_entity dependencies."""
        if cache_ctx is None:
            cache_ctx = MagicMock(return_value=_noop_context())
        return [
            patch("orchestrator.search.indexing.tasks.ENTITY_CONFIG_REGISTRY", registry),
            patch("orchestrator.search.indexing.tasks.db", mock_db),
            patch("orchestrator.search.indexing.tasks.Indexer", mock_indexer_cls),
            patch("orchestrator.search.indexing.tasks.cache_subscription_models", cache_ctx),
        ]

    def _run(
        self,
        registry: dict,
        mock_db: MagicMock,
        mock_indexer_cls: MagicMock,
        cache_ctx: MagicMock | None = None,
        **kwargs,
    ) -> None:
        patches = self._patches(registry, mock_db, mock_indexer_cls, cache_ctx)
        with patches[0], patches[1], patches[2], patches[3]:
            run_indexing_for_entity(EntityType.SUBSCRIPTION, **kwargs)

    # ------------------------------------------------------------------ basic run
    def test_basic_run_calls_indexer_run(self) -> None:
        stmt = _make_mock_stmt()
        config = MagicMock()
        config.get_all_query.return_value = stmt
        registry = {EntityType.SUBSCRIPTION: config}

        mock_db = MagicMock()
        mock_db.session.execute.return_value.scalars.return_value = iter([])

        mock_indexer_instance = MagicMock()
        mock_indexer_cls = MagicMock(return_value=mock_indexer_instance)

        cache_ctx = MagicMock(return_value=_noop_context())

        self._run(registry, mock_db, mock_indexer_cls, cache_ctx)

        mock_indexer_instance.run.assert_called_once()

    # ------------------------------------------------------------------ entity_id forwarding
    def test_entity_id_forwarded_to_get_all_query(self) -> None:
        stmt = _make_mock_stmt()
        config = MagicMock()
        config.get_all_query.return_value = stmt
        registry = {EntityType.SUBSCRIPTION: config}

        mock_db = MagicMock()
        mock_db.session.execute.return_value.scalars.return_value = iter([])
        mock_indexer_cls = MagicMock(return_value=MagicMock())
        cache_ctx = MagicMock(return_value=_noop_context())

        self._run(registry, mock_db, mock_indexer_cls, cache_ctx, entity_id=VALID_UUID)

        config.get_all_query.assert_called_once_with(VALID_UUID)

    # ------------------------------------------------------------------ dry_run / force_index forwarding
    @pytest.mark.parametrize(
        "dry_run,force_index",
        [
            (True, False),
            (False, True),
            (True, True),
        ],
    )
    def test_dry_run_force_index_forwarded_to_indexer(self, dry_run: bool, force_index: bool) -> None:
        stmt = _make_mock_stmt()
        config = MagicMock()
        config.get_all_query.return_value = stmt
        registry = {EntityType.SUBSCRIPTION: config}

        mock_db = MagicMock()
        mock_db.session.execute.return_value.scalars.return_value = iter([])
        mock_indexer_cls = MagicMock(return_value=MagicMock())
        cache_ctx = MagicMock(return_value=_noop_context())

        self._run(registry, mock_db, mock_indexer_cls, cache_ctx, dry_run=dry_run, force_index=force_index)

        _, kwargs = mock_indexer_cls.call_args
        assert kwargs["dry_run"] is dry_run
        assert kwargs["force_index"] is force_index

    # ------------------------------------------------------------------ show_progress triggers count
    def test_show_progress_triggers_entity_count(self) -> None:
        stmt = _make_mock_stmt()
        config = MagicMock()
        config.get_all_query.return_value = stmt
        registry = {EntityType.SUBSCRIPTION: config}

        mock_db = MagicMock()
        mock_db.session.execute.return_value.scalar.return_value = 7
        mock_db.session.execute.return_value.scalars.return_value = iter([])
        mock_indexer_cls = MagicMock(return_value=MagicMock())
        cache_ctx = MagicMock(return_value=_noop_context())

        with (
            patch("orchestrator.search.indexing.tasks.ENTITY_CONFIG_REGISTRY", registry),
            patch("orchestrator.search.indexing.tasks.db", mock_db),
            patch("orchestrator.search.indexing.tasks.Indexer", mock_indexer_cls),
            patch("orchestrator.search.indexing.tasks.cache_subscription_models", cache_ctx),
            patch("orchestrator.search.indexing.tasks._get_entity_count", return_value=7) as mock_count,
        ):
            run_indexing_for_entity(EntityType.SUBSCRIPTION, show_progress=True)

        mock_count.assert_called_once()

    def test_show_progress_false_skips_entity_count(self) -> None:
        stmt = _make_mock_stmt()
        config = MagicMock()
        config.get_all_query.return_value = stmt
        registry = {EntityType.SUBSCRIPTION: config}

        mock_db = MagicMock()
        mock_db.session.execute.return_value.scalars.return_value = iter([])
        mock_indexer_cls = MagicMock(return_value=MagicMock())
        cache_ctx = MagicMock(return_value=_noop_context())

        with (
            patch("orchestrator.search.indexing.tasks.ENTITY_CONFIG_REGISTRY", registry),
            patch("orchestrator.search.indexing.tasks.db", mock_db),
            patch("orchestrator.search.indexing.tasks.Indexer", mock_indexer_cls),
            patch("orchestrator.search.indexing.tasks.cache_subscription_models", cache_ctx),
            patch("orchestrator.search.indexing.tasks._get_entity_count") as mock_count,
        ):
            run_indexing_for_entity(EntityType.SUBSCRIPTION, show_progress=False)

        mock_count.assert_not_called()

    # ------------------------------------------------------------------ Query type handling
    def test_query_type_calls_enable_eagerloads_and_uses_statement(self) -> None:
        mock_query = MagicMock(spec=Query)
        no_eagerload_query = MagicMock(spec=Query)
        mock_stmt = _make_mock_stmt()
        mock_query.enable_eagerloads.return_value = no_eagerload_query
        no_eagerload_query.statement = mock_stmt

        config = MagicMock()
        config.get_all_query.return_value = mock_query
        registry = {EntityType.SUBSCRIPTION: config}

        mock_db = MagicMock()
        mock_db.session.execute.return_value.scalars.return_value = iter([])
        mock_indexer_cls = MagicMock(return_value=MagicMock())
        cache_ctx = MagicMock(return_value=_noop_context())

        self._run(registry, mock_db, mock_indexer_cls, cache_ctx)

        mock_query.enable_eagerloads.assert_called_once_with(False)

    # ------------------------------------------------------------------ Select type handling
    def test_select_type_does_not_access_statement(self) -> None:
        # A non-Query mock: isinstance(q, Query) is False
        mock_select = MagicMock(spec=[])  # no spec so it's NOT a Query
        mock_select.subquery = MagicMock(return_value=MagicMock())
        mock_select.execution_options = MagicMock(return_value=mock_select)

        config = MagicMock()
        config.get_all_query.return_value = mock_select
        registry = {EntityType.SUBSCRIPTION: config}

        mock_db = MagicMock()
        mock_db.session.execute.return_value.scalars.return_value = iter([])
        mock_indexer_cls = MagicMock(return_value=MagicMock())
        cache_ctx = MagicMock(return_value=_noop_context())

        self._run(registry, mock_db, mock_indexer_cls, cache_ctx)

        # .statement should not have been accessed on a non-Query object
        assert not hasattr(mock_select, "_statement_accessed")
        # enable_eagerloads must not have been called
        assert call.enable_eagerloads(False) not in mock_select.mock_calls
