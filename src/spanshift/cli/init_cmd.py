"""spanshift init -- create config, migrations dir, and tracking/lock tables."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from spanshift.config.loader import CONFIG_FILENAME
from spanshift.config.templates import TOML_TEMPLATE
from spanshift.core.connection import AUTH_HELP, get_database, validate_connection
from spanshift.core.lock import MigrationLock
from spanshift.core.tracker import MigrationTracker
from spanshift.exceptions import ConnectionError

console = Console()


def init(
    project_id: str = typer.Option(..., "--project-id", help="GCP project ID"),
    instance_id: str = typer.Option(..., "--instance-id", help="Spanner instance ID"),
    database_id: str = typer.Option(..., "--database-id", help="Spanner database ID"),
    migrations_dir: str = typer.Option("migrations", "--migrations-dir", help="Migrations directory"),
    skip_db: bool = typer.Option(False, "--skip-db", help="Skip Spanner connection; only create config and migrations dir"),
) -> None:
    """Initialize Spanshift in the current project."""
    config_path = Path(CONFIG_FILENAME)
    if config_path.exists():
        console.print(f"[yellow]{CONFIG_FILENAME} already exists, skipping.[/yellow]")
    else:
        content = TOML_TEMPLATE.format(
            project_id=project_id,
            instance_id=instance_id,
            database_id=database_id,
        )
        config_path.write_text(content)
        console.print(f"[green]Created {CONFIG_FILENAME}[/green]")

    # Create migrations directory
    mdir = Path(migrations_dir)
    mdir.mkdir(parents=True, exist_ok=True)
    console.print(f"[green]Migrations directory: {mdir}/[/green]")

    if skip_db:
        console.print("[dim]Skipped Spanner connection (--skip-db).[/dim]")
        return

    # Create tracking + lock tables in Spanner
    from spanshift.config.models import SpannerTarget

    target = SpannerTarget(
        project_id=project_id,
        instance_id=instance_id,
        database_id=database_id,
    )
    try:
        database = get_database(target)
        validate_connection(database)
        tracker = MigrationTracker(database)
        tracker.ensure_table()
        console.print("[green]Tracking table ready.[/green]")
        lock = MigrationLock(database)
        lock.ensure_table()
        console.print("[green]Lock table ready.[/green]")
    except ConnectionError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[yellow]Warning: Could not create tables: {exc}[/yellow]")
        console.print("[dim]Tables will be created automatically on first migration run.[/dim]")
