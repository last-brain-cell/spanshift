"""SHA-256 checksum computation for migration files."""

from __future__ import annotations

import hashlib
from pathlib import Path


def compute_checksum(file_path: Path) -> str:
    """Compute SHA-256 hex digest of a migration file."""
    content = file_path.read_bytes()
    return hashlib.sha256(content).hexdigest()
