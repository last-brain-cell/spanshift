"""MigrationScript class: loads and validates migration files."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from spanshift.core.context import MigrationContext
from spanshift.exceptions import MigrationError
from spanshift.migration.checksum import compute_checksum


@dataclass
class MigrationScript:
    """Represents a single migration file."""

    revision: str
    down_revision: str | None
    description: str
    file_path: Path
    checksum: str
    upgrade_fn: Callable[[MigrationContext], None]
    downgrade_fn: Callable[[MigrationContext], None] | None

    @classmethod
    def from_file(cls, path: Path) -> MigrationScript:
        """Load a migration script from a Python file."""
        module_name = f"_spanshift_migration_{path.stem}"

        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise MigrationError(f"Cannot load migration file: {path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise MigrationError(f"Error executing migration {path}: {exc}") from exc

        # Validate required attributes
        for attr in ("revision", "down_revision", "description", "upgrade"):
            if not hasattr(module, attr):
                raise MigrationError(
                    f"Migration {path} missing required attribute: {attr}"
                )

        return cls(
            revision=module.revision,
            down_revision=module.down_revision,
            description=module.description,
            file_path=path,
            checksum=compute_checksum(path),
            upgrade_fn=module.upgrade,
            downgrade_fn=getattr(module, "downgrade", None),
        )
