"""spanshift history -- show applied migrations with timestamps."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from spanshift.config.loader import load_config
from spanshift.core.connection import get_database
from spanshift.core.tracker import MigrationTracker

console = Console()


def history(
    env: str = typer.Option(None, "--env", help="Environment name"),
) -> None:
    """Show applied migration history with timestamps and execution times."""
    config, spanner_target = load_config(environment=env)
    database = get_database(spanner_target)

    tracker = MigrationTracker(database, config.tracking_table)
    applied = tracker.get_applied()

    if not applied:
        console.print("[yellow]No migrations have been applied.[/yellow]")
        return

    table = Table(title="Migration History")
    table.add_column("Revision", style="cyan")
    table.add_column("Description")
    table.add_column("Applied At")
    table.add_column("Duration", justify="right")

    for m in applied:
        duration = f"{m.execution_time_ms}ms" if m.execution_time_ms is not None else ""
        table.add_row(
            m.version,
            m.description or "",
            str(m.applied_at) if m.applied_at else "",
            duration,
        )

    console.print(table)
