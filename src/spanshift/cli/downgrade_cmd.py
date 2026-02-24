"""spanshift downgrade -- revert applied migrations."""

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


def downgrade(
    steps: int = typer.Argument(1, help="Number of migrations to revert (or 0 for all)"),
    env: str = typer.Option(None, "--env", help="Environment name"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be reverted without executing"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Revert the last N applied migrations."""
    config, spanner_target = load_config(environment=env)
    database = get_database(spanner_target)

    tracker = MigrationTracker(database, config.tracking_table)
    registry = MigrationRegistry(Path(config.migrations_dir))
    registry.load()

    applied = tracker.get_applied_versions()

    # steps=0 means revert all
    actual_steps = steps if steps > 0 else len(registry.chain)
    path = registry.get_downgrade_path(applied, actual_steps)

    if not path:
        console.print("[green]No migrations to revert.[/green]")
        return

    console.print(f"\n[bold red]Reverting {len(path)} migration(s):[/bold red]")
    for s in path:
        console.print(f"  {s.revision} -- {s.description}")

    if not yes and not dry_run:
        typer.confirm("\nRevert these migrations?", abort=True)

    executor = MigrationExecutor(
        database, registry, tracker,
        dry_run=dry_run,
        ddl_timeout=config.ddl_timeout_seconds,
        lock_table=config.lock_table,
        lock_timeout=config.lock_timeout_seconds,
    )
    executor.downgrade(actual_steps)
