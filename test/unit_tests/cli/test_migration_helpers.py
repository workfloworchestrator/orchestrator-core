"""Tests for CLI migration helpers: Alembic operations, version detection, and error handling."""

from pathlib import Path
from unittest import mock

import pytest
from alembic.util.exc import CommandError

from orchestrator.cli.migration_helpers import (
    _insert_preamble,
    create_migration_file,
    remove_core_as_down_revision,
    remove_down_revision_from_text,
)

# ---------------------------------------------------------------------------
# remove_down_revision_from_text — pure function
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Revises line only
        ("Revises: bed6bc0b197a", "Revises:"),
        # down_revision assignment with spaces around =
        ("down_revision = 'bed6bc0b197a'", "down_revision = None"),
        # Full multiline (doctest case)
        (
            "initial\n\nRevises: bed6bc0b197a\n\ndown_revision = 'bed6bc0b197a'\n\ntesting",
            "initial\n\nRevises:\n\ndown_revision = None\n\ntesting",
        ),
        # No space around = — should NOT be matched by down_revision pattern
        (
            "initial\n\nRevises: bed6bc0b197a\n\ndown_revision='bed6bc0b197a'\n\ntesting",
            "initial\n\nRevises:\n\ndown_revision='bed6bc0b197a'\n\ntesting",
        ),
        # Double-quoted down_revision
        ('down_revision = "bed6bc0b197a"', "down_revision = None"),
        # No revision markers present — text is unchanged
        ("no revision here", "no revision here"),
        # Both patterns absent
        ("def upgrade():\n    pass\n", "def upgrade():\n    pass\n"),
    ],
)
def test_remove_down_revision_from_text(text: str, expected: str) -> None:
    assert remove_down_revision_from_text(text) == expected


# ---------------------------------------------------------------------------
# _insert_preamble — pure function
# ---------------------------------------------------------------------------


def test_insert_preamble_inserts_before_upgrade() -> None:
    text = "# header\n\ndef upgrade():\n    pass\n"
    result = _insert_preamble(text, "# preamble line")
    assert "# preamble line\n\ndef upgrade():" in result
    # header should still come first
    assert result.index("# header") < result.index("# preamble line")


def test_insert_preamble_no_upgrade_returns_unchanged() -> None:
    text = "# no upgrade function here\n"
    result = _insert_preamble(text, "# preamble")
    assert result == text


def test_insert_preamble_empty_text() -> None:
    result = _insert_preamble("", "# preamble")
    assert result == ""


# ---------------------------------------------------------------------------
# remove_core_as_down_revision — file I/O
# ---------------------------------------------------------------------------


def test_remove_core_as_down_revision_reads_transforms_writes() -> None:
    original = "Revises: abc123\ndown_revision = 'abc123'\n"
    expected = "Revises:\ndown_revision = None\n"

    fake_migration = mock.MagicMock()
    fake_migration.path = "/fake/migration.py"

    m_open = mock.mock_open(read_data=original)
    with mock.patch("builtins.open", m_open):
        remove_core_as_down_revision(fake_migration)

    handle = m_open()
    written = "".join(call.args[0] for call in handle.write.call_args_list)
    assert written == expected


# ---------------------------------------------------------------------------
# create_migration_file — alembic mocked
# ---------------------------------------------------------------------------


def _make_alembic_config(version_locations: str = "/proj/versions /core/versions") -> mock.MagicMock:
    cfg = mock.MagicMock()
    cfg.get_main_option.return_value = version_locations
    return cfg


def test_create_migration_file_nothing_to_do(capsys: pytest.CaptureFixture) -> None:
    cfg = _make_alembic_config()
    create_migration_file(cfg, "", "", "message")
    captured = capsys.readouterr()
    assert "Nothing to do" in captured.out


@mock.patch("orchestrator.cli.migration_helpers.command")
@mock.patch("orchestrator.cli.migration_helpers.ScriptDirectory")
def test_create_migration_file_generates_revision(
    mock_script_dir: mock.MagicMock, mock_command: mock.MagicMock
) -> None:
    cfg = _make_alembic_config("/proj/versions")
    migration = mock.MagicMock()
    migration.path = "/proj/versions/rev.py"
    mock_command.revision.return_value = migration
    mock_script_dir.from_config.return_value.get_current_head.return_value = "abc123"

    file_content = "def upgrade():\n    pass\ndef downgrade():\n    pass\n"
    m_open = mock.mock_open(read_data=file_content)
    with mock.patch("builtins.open", m_open):
        create_migration_file(cfg, "    op.execute('up')\n", "    op.execute('down')\n", "my message")

    mock_command.revision.assert_called_once()


@mock.patch("orchestrator.cli.migration_helpers.command")
@mock.patch("orchestrator.cli.migration_helpers.ScriptDirectory")
def test_create_migration_file_with_preamble(
    mock_script_dir: mock.MagicMock, mock_command: mock.MagicMock, tmp_path: Path
) -> None:
    cfg = _make_alembic_config("/proj/versions")
    rev_file = tmp_path / "rev.py"
    file_content = "# revision header\n\ndef upgrade():\n    pass\ndef downgrade():\n    pass\n"
    rev_file.write_text(file_content)

    migration = mock.MagicMock()
    migration.path = str(rev_file)
    mock_command.revision.return_value = migration
    mock_script_dir.from_config.return_value.get_current_head.return_value = "abc123"

    create_migration_file(cfg, "    op.execute('up')\n", "    op.execute('down')\n", "msg", preamble="# preamble")

    written = rev_file.read_text()
    assert "# preamble" in written


@mock.patch("orchestrator.cli.migration_helpers.command")
@mock.patch("orchestrator.cli.migration_helpers.ScriptDirectory")
def test_create_migration_file_branch_data_exists_fallback(
    mock_script_dir: mock.MagicMock, mock_command: mock.MagicMock
) -> None:
    cfg = _make_alembic_config("/proj/versions")
    migration = mock.MagicMock()
    migration.path = "/proj/versions/rev.py"
    mock_script_dir.from_config.return_value.get_current_head.return_value = "abc123"

    # First call raises "Branch name 'data' already used by revision"
    mock_command.revision.side_effect = [
        CommandError("Branch name 'data' already used by revision abc"),
        migration,
    ]

    file_content = "def upgrade():\n    pass\ndef downgrade():\n    pass\n"
    m_open = mock.mock_open(read_data=file_content)
    with mock.patch("builtins.open", m_open):
        create_migration_file(cfg, "    op.execute('up')\n", "", "message")

    # Second call should use head="data@head"
    assert mock_command.revision.call_count == 2
    _, second_kwargs = mock_command.revision.call_args
    assert second_kwargs.get("head") == "data@head"


@mock.patch("orchestrator.cli.migration_helpers.command")
@mock.patch("orchestrator.cli.migration_helpers.ScriptDirectory")
def test_create_migration_file_multiple_heads_fallback(
    mock_script_dir: mock.MagicMock, mock_command: mock.MagicMock
) -> None:
    cfg = _make_alembic_config("/proj/versions")
    migration = mock.MagicMock()
    migration.path = "/proj/versions/rev.py"
    mock_script_dir.from_config.return_value.get_current_head.return_value = "abc123"

    mock_command.revision.side_effect = [
        CommandError("The script directory has multiple heads"),
        migration,
    ]

    file_content = "def upgrade():\n    pass\ndef downgrade():\n    pass\n"
    m_open = mock.mock_open(read_data=file_content)
    with mock.patch("builtins.open", m_open):
        create_migration_file(cfg, "    op.execute('up')\n", "", "message")

    assert mock_command.revision.call_count == 2
    _, second_kwargs = mock_command.revision.call_args
    assert second_kwargs.get("head") == "data@head"


@mock.patch("orchestrator.cli.migration_helpers.command")
@mock.patch("orchestrator.cli.migration_helpers.ScriptDirectory")
def test_create_migration_file_database_not_up_to_date_raises(
    mock_script_dir: mock.MagicMock, mock_command: mock.MagicMock
) -> None:
    cfg = _make_alembic_config("/proj/versions")
    mock_script_dir.from_config.return_value.get_current_head.return_value = "abc123"

    # First call: branch already used; second call also raises same error
    branch_error = CommandError("Branch name 'data' already used by revision abc")
    mock_command.revision.side_effect = [branch_error, branch_error]

    with pytest.raises(CommandError, match="Database not up to date"):
        create_migration_file(cfg, "    op.execute('up')\n", "", "message")


@mock.patch("orchestrator.cli.migration_helpers.command")
@mock.patch("orchestrator.cli.migration_helpers.ScriptDirectory")
def test_create_migration_file_unrelated_command_error_propagates(
    mock_script_dir: mock.MagicMock, mock_command: mock.MagicMock
) -> None:
    cfg = _make_alembic_config("/proj/versions")
    mock_script_dir.from_config.return_value.get_current_head.return_value = "abc123"

    mock_command.revision.side_effect = CommandError("Some other unexpected error")

    with pytest.raises(CommandError, match="Some other unexpected error"):
        create_migration_file(cfg, "    op.execute('up')\n", "", "message")
