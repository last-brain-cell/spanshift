"""Reads/writes the spanshift_migrations tracking table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from google.cloud.spanner_v1 import param_types
from google.cloud.spanner_v1.database import Database


TRACKING_TABLE_DDL = """\
CREATE TABLE {table} (
    version STRING(255) NOT NULL,
    description STRING(1024),
    applied_at TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
    checksum STRING(64),
    execution_time_ms INT64,
) PRIMARY KEY (version)"""


@dataclass
class AppliedMigration:
    version: str
    description: str | None
    applied_at: datetime
    checksum: str | None
    execution_time_ms: int | None


class MigrationTracker:
    """Manages the tracking table that records applied migrations."""

    def __init__(self, database: Database, table_name: str = "spanshift_migrations"):
        self._database = database
        self._table = table_name

    def ensure_table(self) -> None:
        """Create the tracking table if it doesn't exist."""
        ddl = TRACKING_TABLE_DDL.format(table=self._table)
        try:
            operation = self._database.update_ddl([ddl])
            operation.result(120)
        except Exception as exc:
            # Table already exists
            if "Duplicate name in schema" in str(exc) or "already exists" in str(exc):
                return
            raise

    def get_applied(self) -> list[AppliedMigration]:
        """Return all applied migrations ordered by version."""
        sql = (
            f"SELECT version, description, applied_at, checksum, execution_time_ms "
            f"FROM {self._table} ORDER BY version"
        )
        results = []
        with self._database.snapshot() as snapshot:
            rows = snapshot.execute_sql(sql)
            for row in rows:
                results.append(
                    AppliedMigration(
                        version=row[0],
                        description=row[1],
                        applied_at=row[2],
                        checksum=row[3],
                        execution_time_ms=row[4],
                    )
                )
        return results

    def get_applied_versions(self) -> set[str]:
        """Return set of applied migration versions."""
        return {m.version for m in self.get_applied()}

    def record_applied(
        self,
        version: str,
        description: str,
        checksum: str,
        execution_time_ms: int,
    ) -> None:
        """Record a migration as applied."""

        def _insert(transaction):
            transaction.execute_update(
                f"INSERT INTO {self._table} "
                f"(version, description, applied_at, checksum, execution_time_ms) "
                f"VALUES (@version, @description, PENDING_COMMIT_TIMESTAMP(), @checksum, @execution_time_ms)",
                params={
                    "version": version,
                    "description": description,
                    "checksum": checksum,
                    "execution_time_ms": execution_time_ms,
                },
                param_types={
                    "version": param_types.STRING,
                    "description": param_types.STRING,
                    "checksum": param_types.STRING,
                    "execution_time_ms": param_types.INT64,
                },
            )

        self._database.run_in_transaction(_insert)

    def remove_applied(self, version: str) -> None:
        """Remove a migration record (used during downgrade)."""

        def _delete(transaction):
            transaction.execute_update(
                f"DELETE FROM {self._table} WHERE version = @version",
                params={"version": version},
                param_types={"version": param_types.STRING},
            )

        self._database.run_in_transaction(_delete)
