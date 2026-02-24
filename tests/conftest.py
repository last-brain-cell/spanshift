"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_migrations(tmp_path: Path) -> Path:
    """Create a temporary migrations directory."""
    mdir = tmp_path / "migrations"
    mdir.mkdir()
    return mdir


@pytest.fixture
def sample_migration_content() -> str:
    """Return a valid migration file content."""
    return '''\
"""Add users table.

Revision: 20260224_120000
Down-revision: None
Created: 2026-02-24T12:00:00
"""

revision = "20260224_120000"
down_revision = None
description = "Add users table"


def upgrade(ctx):
    ctx.execute_ddl([
        """CREATE TABLE users (
            user_id STRING(36) NOT NULL,
            email STRING(255) NOT NULL,
        ) PRIMARY KEY (user_id)""",
    ])


def downgrade(ctx):
    ctx.execute_ddl([
        "DROP TABLE users",
    ])
'''
