"""Tests for checksum computation."""

from pathlib import Path

from spanshift.migration.checksum import compute_checksum


def test_compute_checksum(tmp_path: Path):
    f = tmp_path / "test.py"
    f.write_text("hello world")
    result = compute_checksum(f)
    assert len(result) == 64  # SHA-256 hex digest
    assert result == compute_checksum(f)  # deterministic


def test_checksum_changes_with_content(tmp_path: Path):
    f = tmp_path / "test.py"
    f.write_text("version 1")
    c1 = compute_checksum(f)
    f.write_text("version 2")
    c2 = compute_checksum(f)
    assert c1 != c2
