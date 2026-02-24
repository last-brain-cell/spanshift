"""Tests for migration registry (chain building, validation)."""

from pathlib import Path

import pytest

from spanshift.core.registry import MigrationRegistry
from spanshift.exceptions import InvalidChainError


def _write_migration(mdir: Path, revision: str, down_revision: str | None, desc: str) -> Path:
    down_repr = f'"{down_revision}"' if down_revision else "None"
    content = f'''\
revision = "{revision}"
down_revision = {down_repr}
description = "{desc}"

def upgrade(ctx):
    pass

def downgrade(ctx):
    pass
'''
    path = mdir / f"{revision}_{desc.lower().replace(' ', '_')}.py"
    path.write_text(content)
    return path


def test_empty_registry(tmp_migrations: Path):
    registry = MigrationRegistry(tmp_migrations)
    registry.load()
    assert registry.chain == []
    assert registry.head is None


def test_single_migration(tmp_migrations: Path):
    _write_migration(tmp_migrations, "001", None, "init")
    registry = MigrationRegistry(tmp_migrations)
    registry.load()
    assert len(registry.chain) == 1
    assert registry.head.revision == "001"


def test_chain_ordering(tmp_migrations: Path):
    _write_migration(tmp_migrations, "001", None, "first")
    _write_migration(tmp_migrations, "002", "001", "second")
    _write_migration(tmp_migrations, "003", "002", "third")

    registry = MigrationRegistry(tmp_migrations)
    registry.load()
    assert [s.revision for s in registry.chain] == ["001", "002", "003"]


def test_duplicate_revision(tmp_migrations: Path):
    _write_migration(tmp_migrations, "001", None, "first")
    # Write another file with same revision
    content = '''\
revision = "001"
down_revision = None
description = "duplicate"

def upgrade(ctx):
    pass
'''
    (tmp_migrations / "001_duplicate.py").write_text(content)

    registry = MigrationRegistry(tmp_migrations)
    with pytest.raises(InvalidChainError, match="Duplicate revision"):
        registry.load()


def test_fork_detection(tmp_migrations: Path):
    _write_migration(tmp_migrations, "001", None, "base")
    _write_migration(tmp_migrations, "002a", "001", "fork_a")
    _write_migration(tmp_migrations, "002b", "001", "fork_b")

    registry = MigrationRegistry(tmp_migrations)
    with pytest.raises(InvalidChainError, match="Fork detected"):
        registry.load()


def test_multiple_bases(tmp_migrations: Path):
    _write_migration(tmp_migrations, "001", None, "base_one")
    _write_migration(tmp_migrations, "002", None, "base_two")

    registry = MigrationRegistry(tmp_migrations)
    with pytest.raises(InvalidChainError, match="Multiple base"):
        registry.load()


def test_upgrade_path(tmp_migrations: Path):
    _write_migration(tmp_migrations, "001", None, "first")
    _write_migration(tmp_migrations, "002", "001", "second")
    _write_migration(tmp_migrations, "003", "002", "third")

    registry = MigrationRegistry(tmp_migrations)
    registry.load()

    # Nothing applied
    path = registry.get_upgrade_path(set())
    assert [s.revision for s in path] == ["001", "002", "003"]

    # First applied
    path = registry.get_upgrade_path({"001"})
    assert [s.revision for s in path] == ["002", "003"]

    # Upgrade to specific target
    path = registry.get_upgrade_path(set(), target="002")
    assert [s.revision for s in path] == ["001", "002"]


def test_downgrade_path(tmp_migrations: Path):
    _write_migration(tmp_migrations, "001", None, "first")
    _write_migration(tmp_migrations, "002", "001", "second")
    _write_migration(tmp_migrations, "003", "002", "third")

    registry = MigrationRegistry(tmp_migrations)
    registry.load()

    path = registry.get_downgrade_path({"001", "002", "003"}, steps=2)
    assert [s.revision for s in path] == ["003", "002"]

    path = registry.get_downgrade_path({"001", "002", "003"}, steps=1)
    assert [s.revision for s in path] == ["003"]
