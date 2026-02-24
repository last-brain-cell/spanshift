"""Custom exception hierarchy for Spanshift."""


class SpanshiftError(Exception):
    """Base exception for all Spanshift errors."""


class ConfigError(SpanshiftError):
    """Configuration loading or validation error."""


class ConnectionError(SpanshiftError):
    """Failed to connect to Spanner."""


class LockError(SpanshiftError):
    """Could not acquire or release migration lock."""


class MigrationError(SpanshiftError):
    """Error during migration execution."""


class ChecksumMismatchError(SpanshiftError):
    """Applied migration file was modified after being applied."""

    def __init__(self, version: str, expected: str, actual: str):
        self.version = version
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Checksum mismatch for migration {version}: "
            f"expected {expected}, got {actual}"
        )


class InvalidChainError(SpanshiftError):
    """Migration chain has gaps, forks, or cycles."""


class DowngradeUnavailableError(SpanshiftError):
    """Migration does not have a downgrade function."""
