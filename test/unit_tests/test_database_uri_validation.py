# Copyright 2019-2025 SURF.
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

"""Tests for DATABASE_URI dialect validation in OrchestratorCore.__init__."""

import pytest
from unittest.mock import patch, MagicMock

from orchestrator.app import OrchestratorCore
from orchestrator.settings import AppSettings


def _make_settings(database_uri: str) -> AppSettings:
    """Return an AppSettings instance with the given DATABASE_URI."""
    return AppSettings(DATABASE_URI=database_uri)  # type: ignore[arg-type]


# Patches that suppress all heavyweight side effects of OrchestratorCore.__init__
# so we can exercise only the DATABASE_URI dialect check in isolation.
_INIT_PATCHES = [
    patch("orchestrator.app.initialise_logging"),
    patch("orchestrator.app.init_model_loaders"),
    patch("orchestrator.app.monitor_sqlalchemy_queries"),
    patch("orchestrator.app.init_websocket_manager", return_value=MagicMock(enabled=False)),
    patch("orchestrator.app.init_distlock_manager", return_value=MagicMock()),
    patch("orchestrator.app.get_worker_status_monitor", return_value=MagicMock()),
    patch("orchestrator.app.init_database"),
    patch("orchestrator.app.initialize_default_metrics"),
]


def _apply_patches(patches: list) -> tuple:
    started = [p.start() for p in patches]
    return started


def _stop_patches(patches: list) -> None:
    for p in patches:
        p.stop()


class TestDatabaseUriDialectValidation:
    """DATABASE_URI dialect validation in OrchestratorCore.__init__."""

    def setup_method(self) -> None:
        self._patches = list(_INIT_PATCHES)
        _apply_patches(self._patches)

    def teardown_method(self) -> None:
        _stop_patches(self._patches)

    def test_postgresql_scheme_emits_deprecation_warning(self) -> None:
        """A DATABASE_URI starting with 'postgresql://' must emit a DeprecationWarning."""
        settings = _make_settings("postgresql://nwa:nwa@localhost/orchestrator-core")

        with pytest.warns(DeprecationWarning, match="postgresql\\+psycopg"):
            OrchestratorCore(base_settings=settings)

    def test_deprecation_warning_message_mentions_migration(self) -> None:
        """The DeprecationWarning text should guide users to the correct dialect."""
        settings = _make_settings("postgresql://nwa:nwa@localhost/orchestrator-core")

        with pytest.warns(DeprecationWarning) as record:
            OrchestratorCore(base_settings=settings)

        assert len(record) >= 1
        message = str(record[0].message)
        assert "postgresql+psycopg://" in message
        assert "psycopg2" in message

    def test_psycopg_scheme_emits_no_deprecation_warning(self) -> None:
        """A DATABASE_URI using 'postgresql+psycopg://' must not emit a DeprecationWarning."""
        settings = _make_settings("postgresql+psycopg://nwa:nwa@localhost/orchestrator-core")

        with warnings_as_errors():
            # This should not raise; no DeprecationWarning expected.
            OrchestratorCore(base_settings=settings)


class _DeprecationAsError:
    """Context manager that turns DeprecationWarning into an error inside the block."""

    def __enter__(self) -> "_DeprecationAsError":
        import warnings

        self._prev = warnings.filters[:]
        warnings.filterwarnings("error", category=DeprecationWarning)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool:
        import warnings

        warnings.filters[:] = self._prev
        if exc_type is DeprecationWarning:
            # Convert the warning-turned-error into a readable assertion failure.
            raise AssertionError(f"Unexpected DeprecationWarning raised: {exc_val}") from None
        # Propagate any other exception (or no exception) unchanged.
        return False


def warnings_as_errors() -> "_DeprecationAsError":
    return _DeprecationAsError()
