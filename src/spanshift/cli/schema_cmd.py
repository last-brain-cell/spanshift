"""spanshift schema -- dump current Spanner DDL."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.syntax import Syntax

from spanshift.config.loader import load_config
from spanshift.core.connection import get_database

console = Console()


def schema(
    env: str = typer.Option(None, "--env", help="Environment name"),
) -> None:
    """Dump current database DDL from Spanner."""
    config, spanner_target = load_config(environment=env)
    database = get_database(spanner_target)

    ddl_statements = database.ddl_statements

    if not ddl_statements:
        console.print("[yellow]No DDL statements found (empty database).[/yellow]")
        return

    console.print(f"[bold]Database DDL ({len(ddl_statements)} statements):[/bold]\n")
    for stmt in ddl_statements:
        syntax = Syntax(stmt + ";", "sql", theme="monokai", word_wrap=True)
        console.print(syntax)
        console.print()
