"""spanshift current -- show current head revision."""

from __future__ import annotations

import typer
from rich.console import Console

from spanshift.config.loader import load_config
from spanshift.core.connection import get_database
from spanshift.core.tracker import MigrationTracker

console = Console()


def current(
    env: str = typer.Option(None, "--env", help="Environment name"),
) -> None:
    """Show the current (latest applied) migration revision."""
    config, spanner_target = load_config(environment=env)
    database = get_database(spanner_target)

    tracker = MigrationTracker(database, config.tracking_table)
    applied = tracker.get_applied()

    if not applied:
        console.print("[yellow]No migrations have been applied.[/yellow]")
        return

    latest = applied[-1]
    console.print(f"[bold]{latest.version}[/bold] -- {latest.description}")
    console.print(f"Applied at: {latest.applied_at}")
