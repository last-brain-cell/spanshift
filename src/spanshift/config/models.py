"""Pydantic models for Spanshift configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class SpannerTarget(BaseModel):
    """Connection details for a Spanner database."""

    project_id: str
    instance_id: str
    database_id: str
    credentials_path: str | None = None


class SpanshiftConfig(BaseModel):
    """Top-level Spanshift configuration."""

    migrations_dir: Path = Path("migrations")
    naming: Literal["timestamp", "sequential"] = "timestamp"
    tracking_table: str = "spanshift_migrations"
    lock_table: str = "spanshift_lock"
    lock_timeout_seconds: int = 300
    ddl_timeout_seconds: int = 600
    environments: dict[str, SpannerTarget] = {}
    default_environment: str = "default"
