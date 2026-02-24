"""Tests for migration executor (checksum verification, dry-run)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spanshift.core.executor import MigrationExecutor
from spanshift.core.registry import MigrationRegistry
from spanshift.core.tracker import AppliedMigration, MigrationTracker
from spanshift.exceptions import ChecksumMismatchError


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


def test_verify_checksums_ok(tmp_path: Path):
    mdir = tmp_path / "migrations"
    mdir.mkdir()
    p = _write_migration(mdir, "001", None, "init")

    registry = MigrationRegistry(mdir)
    registry.load()

    from spanshift.migration.checksum import compute_checksum

    tracker = MagicMock(spec=MigrationTracker)
    tracker.get_applied.return_value = [
        AppliedMigration(
            version="001",
            description="init",
            applied_at=None,
            checksum=compute_checksum(p),
            execution_time_ms=100,
        )
    ]

    db = MagicMock()
    executor = MigrationExecutor(db, registry, tracker, dry_run=True)
    mismatches = executor.verify_checksums()
    assert mismatches == []


def test_verify_checksums_mismatch(tmp_path: Path):
    mdir = tmp_path / "migrations"
    mdir.mkdir()
    _write_migration(mdir, "001", None, "init")

    registry = MigrationRegistry(mdir)
    registry.load()

    tracker = MagicMock(spec=MigrationTracker)
    tracker.get_applied.return_value = [
        AppliedMigration(
            version="001",
            description="init",
            applied_at=None,
            checksum="0000000000000000000000000000000000000000000000000000000000000000",
            execution_time_ms=100,
        )
    ]

    db = MagicMock()
    executor = MigrationExecutor(db, registry, tracker, dry_run=True)
    mismatches = executor.verify_checksums()
    assert len(mismatches) == 1
    assert mismatches[0].version == "001"


def test_upgrade_dry_run_does_not_lock(tmp_path: Path):
    mdir = tmp_path / "migrations"
    mdir.mkdir()
    _write_migration(mdir, "001", None, "init")

    registry = MigrationRegistry(mdir)
    registry.load()

    tracker = MagicMock(spec=MigrationTracker)
    tracker.get_applied.return_value = []
    tracker.get_applied_versions.return_value = set()

    db = MagicMock()
    executor = MigrationExecutor(db, registry, tracker, dry_run=True)

    with patch("spanshift.core.executor.MigrationLock") as MockLock:
        result = executor.upgrade()
        MockLock.assert_not_called()

    assert len(result) == 1
    assert result[0].revision == "001"


def test_upgrade_acquires_lock(tmp_path: Path):
    mdir = tmp_path / "migrations"
    mdir.mkdir()
    _write_migration(mdir, "001", None, "init")

    registry = MigrationRegistry(mdir)
    registry.load()

    tracker = MagicMock(spec=MigrationTracker)
    tracker.get_applied.return_value = []
    tracker.get_applied_versions.return_value = set()

    db = MagicMock()
    executor = MigrationExecutor(db, registry, tracker, dry_run=False)

    with patch("spanshift.core.executor.MigrationLock") as MockLock:
        mock_lock_instance = MagicMock()
        MockLock.return_value = mock_lock_instance
        mock_lock_instance.__enter__ = MagicMock(return_value=mock_lock_instance)
        mock_lock_instance.__exit__ = MagicMock(return_value=False)

        result = executor.upgrade()

        MockLock.assert_called_once()
        mock_lock_instance.ensure_table.assert_called_once()
        mock_lock_instance.__enter__.assert_called_once()

    assert len(result) == 1


def test_upgrade_fails_on_checksum_mismatch(tmp_path: Path):
    mdir = tmp_path / "migrations"
    mdir.mkdir()
    _write_migration(mdir, "001", None, "init")
    _write_migration(mdir, "002", "001", "second")

    registry = MigrationRegistry(mdir)
    registry.load()

    tracker = MagicMock(spec=MigrationTracker)
    tracker.get_applied.return_value = [
        AppliedMigration(
            version="001",
            description="init",
            applied_at=None,
            checksum="bad_checksum",
            execution_time_ms=100,
        )
    ]
    tracker.get_applied_versions.return_value = {"001"}

    db = MagicMock()
    executor = MigrationExecutor(db, registry, tracker, dry_run=False)

    with pytest.raises(ChecksumMismatchError):
        executor.upgrade()
