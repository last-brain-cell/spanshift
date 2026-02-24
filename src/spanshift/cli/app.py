"""Typer app, top-level CLI group."""

from __future__ import annotations

import typer

from spanshift.cli.current_cmd import current
from spanshift.cli.downgrade_cmd import downgrade
from spanshift.cli.history_cmd import history
from spanshift.cli.init_cmd import init
from spanshift.cli.new_cmd import new
from spanshift.cli.schema_cmd import schema
from spanshift.cli.status_cmd import status
from spanshift.cli.upgrade_cmd import upgrade

app = typer.Typer(
    name="spanshift",
    help="Schema migration tool for Google Cloud Spanner.",
    no_args_is_help=True,
)

app.command()(init)
app.command()(new)
app.command()(upgrade)
app.command()(downgrade)
app.command()(status)
app.command()(current)
app.command()(history)
app.command()(schema)
