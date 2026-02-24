"""spanshift status -- show applied/pending migrations."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from spanshift.config.loader import load_config
from spanshift.core.connection import get_database
from spanshift.core.registry import MigrationRegistry
from spanshift.core.tracker import MigrationTracker

console = Console()


def status(
    env: str = typer.Option(None, "--env", help="Environment name"),
) -> None:
    """Show migration status (applied/pending)."""
    config, spanner_target = load_config(environment=env)
    database = get_database(spanner_target)

    tracker = MigrationTracker(database, config.tracking_table)
    registry = MigrationRegistry(Path(config.migrations_dir))
    registry.load()

    applied_migrations = {m.version: m for m in tracker.get_applied()}

    table = Table(title="Migration Status")
    table.add_column("Revision", style="cyan")
    table.add_column("Description")
    table.add_column("Status")
    table.add_column("Applied At")
    table.add_column("Checksum")

    for script in registry.chain:
        applied = applied_migrations.get(script.revision)
        if applied:
            checksum_ok = applied.checksum == script.checksum
            checksum_display = (
                "[green]OK[/green]" if checksum_ok else "[red]MISMATCH[/red]"
            )
            table.add_row(
                script.revision,
                script.description,
                "[green]Applied[/green]",
                str(applied.applied_at) if applied.applied_at else "",
                checksum_display,
            )
        else:
            table.add_row(
                script.revision,
                script.description,
                "[yellow]Pending[/yellow]",
                "",
                "",
            )

    console.print(table)
