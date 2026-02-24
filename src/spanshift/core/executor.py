"""Orchestrates running migrations (upgrade and downgrade)."""

from __future__ import annotations

import time

from google.cloud.spanner_v1.database import Database
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from spanshift.core.context import MigrationContext
from spanshift.core.lock import MigrationLock
from spanshift.core.registry import MigrationRegistry
from spanshift.core.tracker import MigrationTracker
from spanshift.exceptions import (
    ChecksumMismatchError,
    DowngradeUnavailableError,
    MigrationError,
)
from spanshift.migration.script import MigrationScript

console = Console()


class MigrationExecutor:
    """Runs migrations against a Spanner database."""

    def __init__(
        self,
        database: Database,
        registry: MigrationRegistry,
        tracker: MigrationTracker,
        *,
        dry_run: bool = False,
        ddl_timeout: int = 600,
        lock_table: str = "spanshift_lock",
        lock_timeout: int = 300,
    ):
        self._database = database
        self._registry = registry
        self._tracker = tracker
        self._dry_run = dry_run
        self._ddl_timeout = ddl_timeout
        self._lock_table = lock_table
        self._lock_timeout = lock_timeout

    def verify_checksums(self) -> list[ChecksumMismatchError]:
        """Verify checksums of all applied migrations against current files.

        Returns a list of mismatch errors (empty if all OK).
        """
        applied = {m.version: m for m in self._tracker.get_applied()}
        scripts = {s.revision: s for s in self._registry.chain}
        mismatches = []

        for version, applied_migration in applied.items():
            script = scripts.get(version)
            if script is None:
                continue
            if (
                applied_migration.checksum
                and applied_migration.checksum != script.checksum
            ):
                mismatches.append(
                    ChecksumMismatchError(
                        version=version,
                        expected=applied_migration.checksum,
                        actual=script.checksum,
                    )
                )

        return mismatches

    def upgrade(self, target: str | None = None) -> list[MigrationScript]:
        """Apply pending migrations. Returns list of applied scripts."""
        applied_versions = self._tracker.get_applied_versions()
        path = self._registry.get_upgrade_path(applied_versions, target)

        if not path:
            console.print("[green]No pending migrations.[/green]")
            return []

        # Verify checksums before applying
        mismatches = self.verify_checksums()
        if mismatches:
            console.print("[bold red]Checksum verification failed:[/bold red]")
            for m in mismatches:
                console.print(f"  [red]{m}[/red]")
            raise mismatches[0]

        console.print(f"[bold]Applying {len(path)} migration(s)...[/bold]")

        if self._dry_run:
            return self._run_path(path, direction="upgrade")

        lock = MigrationLock(
            self._database, self._lock_table, self._lock_timeout
        )
        lock.ensure_table()
        with lock:
            return self._run_path(path, direction="upgrade")

    def downgrade(self, steps: int = 1) -> list[MigrationScript]:
        """Revert the last N applied migrations. Returns list of reverted scripts."""
        applied_versions = self._tracker.get_applied_versions()
        path = self._registry.get_downgrade_path(applied_versions, steps)

        if not path:
            console.print("[green]No migrations to revert.[/green]")
            return []

        console.print(f"[bold]Reverting {len(path)} migration(s)...[/bold]")

        if self._dry_run:
            return self._run_path(path, direction="downgrade")

        lock = MigrationLock(
            self._database, self._lock_table, self._lock_timeout
        )
        lock.ensure_table()
        with lock:
            return self._run_path(path, direction="downgrade")

    def _run_path(
        self, path: list[MigrationScript], *, direction: str
    ) -> list[MigrationScript]:
        """Execute a list of migrations sequentially."""
        completed = []
        for script in path:
            self._run_single(script, direction=direction)
            completed.append(script)
        return completed

    def _run_single(self, script: MigrationScript, *, direction: str) -> None:
        """Execute a single migration in the given direction."""
        label = f"{script.revision} ({script.description})"

        if direction == "downgrade" and script.downgrade_fn is None:
            raise DowngradeUnavailableError(
                f"Migration {label} does not define a downgrade function"
            )

        ctx = MigrationContext(
            self._database,
            dry_run=self._dry_run,
            ddl_timeout=self._ddl_timeout,
        )

        fn = script.upgrade_fn if direction == "upgrade" else script.downgrade_fn
        action = "Applying" if direction == "upgrade" else "Reverting"

        start = time.monotonic()
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn(f"  {action}: {label}..."),
                TimeElapsedColumn(),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("", total=None)
                fn(ctx)
        except Exception as exc:
            console.print(f"  {action}: {label}... [red]FAILED[/red]")
            raise MigrationError(f"Migration {label} failed: {exc}") from exc
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if self._dry_run:
            console.print(f"  {action}: {label}... [yellow]DRY RUN[/yellow]")
            if ctx.collected_ddl:
                for stmt in ctx.collected_ddl:
                    console.print(f"    [dim]{stmt}[/dim]")
        else:
            if direction == "upgrade":
                self._tracker.record_applied(
                    version=script.revision,
                    description=script.description,
                    checksum=script.checksum,
                    execution_time_ms=elapsed_ms,
                )
            else:
                self._tracker.remove_applied(script.revision)
            console.print(f"  {action}: {label}... [green]OK[/green] ({elapsed_ms}ms)")
