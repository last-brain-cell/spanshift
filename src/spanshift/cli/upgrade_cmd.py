"""spanshift upgrade -- apply pending migrations."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from spanshift.config.loader import load_config
from spanshift.core.connection import get_database
from spanshift.core.executor import MigrationExecutor
from spanshift.core.registry import MigrationRegistry
from spanshift.core.tracker import MigrationTracker

console = Console()


def upgrade(
    target: str = typer.Argument(None, help="Target revision (default: apply all pending)"),
    env: str = typer.Option(None, "--env", help="Environment name"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be applied without executing"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Apply pending migrations."""
    config, spanner_target = load_config(environment=env)
    database = get_database(spanner_target)

    tracker = MigrationTracker(database, config.tracking_table)
    tracker.ensure_table()

    registry = MigrationRegistry(Path(config.migrations_dir))
    registry.load()

    applied = tracker.get_applied_versions()
    path = registry.get_upgrade_path(applied, target)

    if not path:
        console.print("[green]No pending migrations.[/green]")
        return

    console.print(f"\n[bold]Pending migrations ({len(path)}):[/bold]")
    for s in path:
        console.print(f"  {s.revision} -- {s.description}")

    if not yes and not dry_run:
        typer.confirm("\nApply these migrations?", abort=True)

    executor = MigrationExecutor(
        database, registry, tracker,
        dry_run=dry_run,
        ddl_timeout=config.ddl_timeout_seconds,
        lock_table=config.lock_table,
        lock_timeout=config.lock_timeout_seconds,
    )
    executor.upgrade(target)
