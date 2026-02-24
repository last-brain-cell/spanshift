"""Discovers, loads, orders, and validates migration files."""

from __future__ import annotations

from pathlib import Path

from spanshift.exceptions import InvalidChainError
from spanshift.migration.script import MigrationScript


class MigrationRegistry:
    """Discovers and manages the ordered chain of migration scripts."""

    def __init__(self, migrations_dir: Path):
        self._migrations_dir = migrations_dir
        self._scripts: dict[str, MigrationScript] = {}
        self._chain: list[MigrationScript] = []

    @property
    def chain(self) -> list[MigrationScript]:
        """Ordered list of migrations from base to head."""
        return list(self._chain)

    @property
    def head(self) -> MigrationScript | None:
        """The latest migration in the chain."""
        return self._chain[-1] if self._chain else None

    def load(self) -> None:
        """Discover and load all migration files, then build the chain."""
        self._scripts.clear()
        self._chain.clear()

        if not self._migrations_dir.is_dir():
            return

        files = sorted(self._migrations_dir.glob("*.py"))
        for f in files:
            if f.name.startswith("__"):
                continue
            script = MigrationScript.from_file(f)
            if script.revision in self._scripts:
                raise InvalidChainError(
                    f"Duplicate revision '{script.revision}' found in "
                    f"{script.file_path} and {self._scripts[script.revision].file_path}"
                )
            self._scripts[script.revision] = script

        self._build_chain()

    def _build_chain(self) -> None:
        """Build the ordered chain from down_revision links."""
        if not self._scripts:
            return

        # Find the base (down_revision is None)
        bases = [s for s in self._scripts.values() if s.down_revision is None]
        if len(bases) == 0:
            raise InvalidChainError("No base migration found (down_revision = None)")
        if len(bases) > 1:
            raise InvalidChainError(
                f"Multiple base migrations found: {[b.revision for b in bases]}"
            )

        # Build forward map: down_revision -> revision
        forward: dict[str | None, list[str]] = {}
        for s in self._scripts.values():
            forward.setdefault(s.down_revision, []).append(s.revision)

        # Check for forks
        for parent, children in forward.items():
            if len(children) > 1:
                raise InvalidChainError(
                    f"Fork detected: revision '{parent}' has multiple successors: {children}"
                )

        # Walk the chain
        current = bases[0]
        visited: set[str] = set()
        while True:
            if current.revision in visited:
                raise InvalidChainError(
                    f"Cycle detected at revision '{current.revision}'"
                )
            visited.add(current.revision)
            self._chain.append(current)

            next_revisions = forward.get(current.revision, [])
            if not next_revisions:
                break
            current = self._scripts[next_revisions[0]]

        # Check for orphans
        if len(self._chain) != len(self._scripts):
            orphans = set(self._scripts.keys()) - visited
            raise InvalidChainError(
                f"Orphaned migrations not connected to the chain: {orphans}"
            )

    def get_upgrade_path(self, applied: set[str], target: str | None = None) -> list[MigrationScript]:
        """Return migrations to apply (pending, up to optional target)."""
        path = []
        for script in self._chain:
            if script.revision in applied:
                continue
            path.append(script)
            if target and script.revision == target:
                break
        return path

    def get_downgrade_path(self, applied: set[str], steps: int) -> list[MigrationScript]:
        """Return migrations to revert, in reverse order."""
        applied_in_order = [s for s in self._chain if s.revision in applied]
        return list(reversed(applied_in_order[-steps:]))
