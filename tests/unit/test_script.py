"""Tests for migration script loading."""

from pathlib import Path

import pytest

from spanshift.exceptions import MigrationError
from spanshift.migration.script import MigrationScript


def test_load_valid_script(tmp_migrations: Path, sample_migration_content: str):
    f = tmp_migrations / "20260224_120000_add_users.py"
    f.write_text(sample_migration_content)

    script = MigrationScript.from_file(f)
    assert script.revision == "20260224_120000"
    assert script.down_revision is None
    assert script.description == "Add users table"
    assert script.upgrade_fn is not None
    assert script.downgrade_fn is not None
    assert len(script.checksum) == 64


def test_load_script_missing_attribute(tmp_migrations: Path):
    f = tmp_migrations / "bad.py"
    f.write_text('revision = "001"\n')

    with pytest.raises(MigrationError, match="missing required attribute"):
        MigrationScript.from_file(f)


def test_load_script_syntax_error(tmp_migrations: Path):
    f = tmp_migrations / "broken.py"
    f.write_text("def upgrade(:\n")

    with pytest.raises(MigrationError, match="Error executing"):
        MigrationScript.from_file(f)
