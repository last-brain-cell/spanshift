"""spanshift new -- generate a new migration file."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console

from spanshift.config.loader import load_config
from spanshift.config.templates import MIGRATION_TEMPLATE
from spanshift.core.registry import MigrationRegistry
from spanshift.exceptions import ConfigError

console = Console()


def new(
    description: str = typer.Argument(..., help="Short description of the migration"),
    env: str = typer.Option(None, "--env", help="Environment name"),
) -> None:
    """Generate a new migration file."""
    try:
        config, _target = load_config(environment=env)
    except ConfigError:
        # Allow creating migrations without a valid target (just need migrations_dir)
        from spanshift.config.models import SpanshiftConfig

        config = SpanshiftConfig()

    migrations_dir = Path(config.migrations_dir)
    migrations_dir.mkdir(parents=True, exist_ok=True)

    # Determine revision ID
    now = datetime.now(timezone.utc)
    revision = now.strftime("%Y%m%d_%H%M%S")

    # Find current head for down_revision
    registry = MigrationRegistry(migrations_dir)
    try:
        registry.load()
    except Exception:
        pass  # Empty dir is fine
    head = registry.head
    down_revision = head.revision if head else None

    # Slugify description for filename
    slug = description.lower().replace(" ", "_").replace("-", "_")
    slug = "".join(c for c in slug if c.isalnum() or c == "_")
    filename = f"{revision}_{slug}.py"

    down_revision_repr = f'"{down_revision}"' if down_revision else "None"

    content = MIGRATION_TEMPLATE.format(
        description=description,
        revision=revision,
        down_revision=down_revision or "None",
        down_revision_repr=down_revision_repr,
        created=now.isoformat(),
    )

    filepath = migrations_dir / filename
    filepath.write_text(content)
    console.print(f"[green]Created migration: {filepath}[/green]")
