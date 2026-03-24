from types import SimpleNamespace
from unittest import mock

from typer.testing import CliRunner

import orchestrator.cli.database as database_cli
from orchestrator.cli.database import app as db_app

runner = CliRunner()


def _mock_alembic_cfg(cfg=None):
    """Patch alembic_cfg to return a mock config object, avoiding alembic.ini reads."""
    if cfg is None:
        cfg = SimpleNamespace(
            get_main_option=mock.Mock(return_value=""),
            set_main_option=mock.Mock(),
        )
    return mock.patch.object(database_cli, "alembic_cfg", return_value=cfg)


# --- alembic_cfg ---


def test_alembic_cfg_appends_version_locations():
    mock_cfg = mock.Mock()
    mock_cfg.get_main_option.return_value = "existing/path"
    with mock.patch("orchestrator.cli.database.Config", return_value=mock_cfg):
        database_cli.alembic_cfg()
    mock_cfg.set_main_option.assert_called_once()
    call_args = mock_cfg.set_main_option.call_args[0]
    assert call_args[0] == "version_locations"
    assert "existing/path" in call_args[1]
    assert "versions/schema" in call_args[1]


# --- heads ---


def test_heads_delegates_to_alembic():
    with (
        _mock_alembic_cfg(),
        mock.patch("orchestrator.cli.database.command") as mock_cmd,
    ):
        result = runner.invoke(db_app, ["heads"])
    assert result.exit_code == 0
    mock_cmd.heads.assert_called_once()


# --- merge ---


def test_merge_delegates_to_alembic():
    with (
        _mock_alembic_cfg(),
        mock.patch("orchestrator.cli.database.command") as mock_cmd,
    ):
        # merge takes a single REVISIONS string argument
        result = runner.invoke(db_app, ["merge", "abc123 def456", "--message", "merge two heads"])
    assert result.exit_code == 0
    mock_cmd.merge.assert_called_once()
    call_kwargs = mock_cmd.merge.call_args[1]
    assert call_kwargs["message"] == "merge two heads"


# --- upgrade ---


def test_upgrade_delegates_to_alembic():
    with (
        _mock_alembic_cfg(),
        mock.patch("orchestrator.cli.database.command") as mock_cmd,
    ):
        result = runner.invoke(db_app, ["upgrade", "head"])
    assert result.exit_code == 0
    mock_cmd.upgrade.assert_called_once()


# --- downgrade ---


def test_downgrade_delegates_to_alembic():
    with (
        _mock_alembic_cfg(),
        mock.patch("orchestrator.cli.database.command") as mock_cmd,
    ):
        result = runner.invoke(db_app, ["downgrade", "abc123"])
    assert result.exit_code == 0
    mock_cmd.downgrade.assert_called_once()


def test_downgrade_default_revision_is_minus_one():
    with (
        _mock_alembic_cfg(),
        mock.patch("orchestrator.cli.database.command") as mock_cmd,
    ):
        result = runner.invoke(db_app, ["downgrade"])
    assert result.exit_code == 0
    call_args = mock_cmd.downgrade.call_args[0]
    assert "-1" in call_args


# --- revision ---


def test_revision_delegates_to_alembic():
    with (
        _mock_alembic_cfg(),
        mock.patch("orchestrator.cli.database.command") as mock_cmd,
        mock.patch("orchestrator.cli.database.create_data_head_if_not_exists"),
    ):
        result = runner.invoke(db_app, ["revision", "--message", "add table"])
    assert result.exit_code == 0
    mock_cmd.revision.assert_called_once()


# --- history ---


def test_history_delegates_to_alembic():
    with (
        _mock_alembic_cfg(),
        mock.patch("orchestrator.cli.database.command") as mock_cmd,
    ):
        result = runner.invoke(db_app, ["history"])
    assert result.exit_code == 0
    mock_cmd.history.assert_called_once()


# --- init ---


def test_init_raises_on_existing_directory(tmp_path):
    existing_dir = tmp_path / "migrations"
    existing_dir.mkdir()
    (existing_dir / "dummy").touch()
    with mock.patch.object(database_cli, "migration_dir", str(existing_dir)):
        result = runner.invoke(db_app, ["init"])
    assert result.exit_code != 0


# --- migrate_domain_models --test ---


def test_migrate_domain_models_test_returns_sql_tuple():
    sql_result = (["SELECT 1"], ["SELECT 2"])
    with (
        _mock_alembic_cfg(),
        mock.patch("orchestrator.cli.database.app_settings", SimpleNamespace(TESTING=True)),
        mock.patch("orchestrator.cli.database.create_domain_models_migration_sql", return_value=sql_result),
    ):
        result = runner.invoke(db_app, ["migrate-domain-models", "test migration", "--test"])
    assert result.exit_code == 0


# --- migrate_workflows --test ---


def test_migrate_workflows_test_returns_wizard_results():
    wizard_result = ([], [])
    with (
        _mock_alembic_cfg(),
        mock.patch("orchestrator.cli.database.app_settings", SimpleNamespace(TESTING=True)),
        mock.patch("orchestrator.cli.database.create_workflows_migration_wizard", return_value=wizard_result),
    ):
        result = runner.invoke(db_app, ["migrate-workflows", "test migration", "--test"])
    assert result.exit_code == 0


# --- migrate_tasks --test ---


def test_migrate_tasks_test_returns_wizard_results():
    wizard_result = ([], [])
    with (
        _mock_alembic_cfg(),
        mock.patch("orchestrator.cli.database.app_settings", SimpleNamespace(TESTING=True)),
        mock.patch("orchestrator.cli.database.create_tasks_migration_wizard", return_value=wizard_result),
    ):
        result = runner.invoke(db_app, ["migrate-tasks", "test migration", "--test"])
    assert result.exit_code == 0
