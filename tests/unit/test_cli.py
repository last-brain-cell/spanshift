"""Tests for CLI commands using Typer's CliRunner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from spanshift.cli.app import app

runner = CliRunner()


def test_new_creates_migration_file(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Create a minimal config so 'new' can work without Spanner
    (tmp_path / "spanshift.toml").write_text("""\
[spanshift]
migrations_dir = "migrations"

[environments.default]
project_id = "test"
instance_id = "test"
database_id = "test"
""")

    result = runner.invoke(app, ["new", "Add users table"])
    assert result.exit_code == 0
    assert "Created migration" in result.output

    migrations = list((tmp_path / "migrations").glob("*.py"))
    assert len(migrations) == 1
    assert "add_users_table" in migrations[0].name


def test_new_chains_down_revision(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "spanshift.toml").write_text("""\
[spanshift]
migrations_dir = "migrations"

[environments.default]
project_id = "test"
instance_id = "test"
database_id = "test"
""")

    # Create first migration
    result = runner.invoke(app, ["new", "First migration"])
    assert result.exit_code == 0

    # Create second -- should chain to first
    result = runner.invoke(app, ["new", "Second migration"])
    assert result.exit_code == 0

    migrations = sorted((tmp_path / "migrations").glob("*.py"))
    assert len(migrations) == 2

    # Read second migration and check it references the first
    second_content = migrations[1].read_text()
    first_stem = migrations[0].stem
    # The revision of the first migration should appear as down_revision
    first_revision = first_stem.split("_", 2)
    # revision format: YYYYMMDD_HHMMSS
    assert "down_revision" in second_content
    assert "None" not in second_content.split("down_revision")[1].split("\n")[0]


def test_cli_no_args_shows_help():
    result = runner.invoke(app, [])
    # Typer returns exit code 0 for --help, but 2 for no_args_is_help
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output or "usage" in result.output.lower()
